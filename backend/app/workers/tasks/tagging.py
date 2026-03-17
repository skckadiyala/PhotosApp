import logging
import os

from app.config import get_settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

# Lazy-loaded model
_clip_model = None
_clip_preprocess = None
_clip_tokenizer = None


def _get_clip():
    global _clip_model, _clip_preprocess, _clip_tokenizer
    if _clip_model is None:
        import open_clip
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="laion2b_s34b_b79k"
        )
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        model.eval()
        _clip_model = model
        _clip_preprocess = preprocess
        _clip_tokenizer = tokenizer
    return _clip_model, _clip_preprocess, _clip_tokenizer


# Common tags to match against
TAG_CATEGORIES = {
    "scene": [
        "beach", "mountain", "forest", "city", "sunset", "sunrise", "night",
        "indoor", "outdoor", "garden", "park", "restaurant", "office",
        "wedding", "concert", "birthday party", "graduation",
    ],
    "object": [
        "car", "dog", "cat", "food", "flower", "building", "tree",
        "water", "sky", "snow", "rain", "book", "phone", "laptop",
    ],
    "color": [
        "colorful", "black and white", "warm tones", "cool tones",
    ],
}


@celery_app.task(name="auto_tag_photo", bind=True, max_retries=2)
def auto_tag_photo(self, photo_id: str, file_path: str):
    """Use CLIP to auto-tag a photo with scene/object labels."""
    try:
        import torch
        from PIL import Image

        full_path = os.path.join(settings.photos_dir, file_path)
        if not os.path.isfile(full_path):
            logger.error("Photo file not found: %s", full_path)
            return None

        model, preprocess, tokenizer = _get_clip()

        image = preprocess(Image.open(full_path).convert("RGB")).unsqueeze(0)

        all_tags = []
        results = []

        for category, tags in TAG_CATEGORIES.items():
            text = tokenizer([f"a photo of {tag}" for tag in tags])

            with torch.no_grad():
                image_features = model.encode_image(image)
                text_features = model.encode_text(text)

                image_features /= image_features.norm(dim=-1, keepdim=True)
                text_features /= text_features.norm(dim=-1, keepdim=True)

                similarity = (image_features @ text_features.T).squeeze(0)
                probs = similarity.softmax(dim=-1)

            for tag, prob in zip(tags, probs):
                score = float(prob)
                if score > 0.1:  # Threshold
                    results.append({
                        "tag": tag,
                        "category": category,
                        "confidence": round(score, 3),
                    })

        # Sort by confidence and take top tags
        results.sort(key=lambda x: x["confidence"], reverse=True)
        results = results[:15]

        logger.info("Auto-tagged photo %s with %d tags", photo_id, len(results))
        return {"photo_id": photo_id, "tags": results}

    except Exception as exc:
        logger.exception("Auto-tagging failed for %s", photo_id)
        raise self.retry(exc=exc, countdown=60)
