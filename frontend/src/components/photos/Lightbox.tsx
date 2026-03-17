import { useEffect, useCallback } from 'react';
import { getOriginalUrl } from '../../api/photos';
import { useUIStore } from '../../stores/uiStore';
import AuthImage from '../common/AuthImage';
import type { Photo } from '../../types/photo';

interface Props {
  photos: Photo[];
}

export default function Lightbox({ photos }: Props) {
  const { lightboxOpen, lightboxPhotoId, closeLightbox, openLightbox } = useUIStore();

  const currentIndex = photos.findIndex((p) => p.id === lightboxPhotoId);

  const goNext = useCallback(() => {
    if (currentIndex < photos.length - 1) {
      openLightbox(photos[currentIndex + 1].id);
    }
  }, [currentIndex, photos, openLightbox]);

  const goPrev = useCallback(() => {
    if (currentIndex > 0) {
      openLightbox(photos[currentIndex - 1].id);
    }
  }, [currentIndex, photos, openLightbox]);

  useEffect(() => {
    if (!lightboxOpen) return;

    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeLightbox();
      if (e.key === 'ArrowRight') goNext();
      if (e.key === 'ArrowLeft') goPrev();
    };

    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [lightboxOpen, closeLightbox, goNext, goPrev]);

  if (!lightboxOpen || !lightboxPhotoId || currentIndex === -1) return null;

  const photo = photos[currentIndex];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90">
      {/* Close button */}
      <button
        onClick={closeLightbox}
        className="absolute right-4 top-4 z-10 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
      >
        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Previous */}
      {currentIndex > 0 && (
        <button
          onClick={goPrev}
          className="absolute left-4 z-10 rounded-full bg-black/50 p-3 text-white hover:bg-black/70"
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      )}

      {/* Image */}
      <AuthImage
        src={getOriginalUrl(photo.id)}
        alt={photo.file_name}
        className="max-h-[90vh] max-w-[90vw] object-contain"
      />

      {/* Next */}
      {currentIndex < photos.length - 1 && (
        <button
          onClick={goNext}
          className="absolute right-4 z-10 rounded-full bg-black/50 p-3 text-white hover:bg-black/70"
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      {/* Info bar */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-4 text-white">
        <p className="text-sm font-medium">{photo.file_name}</p>
        {photo.taken_at && (
          <p className="text-xs text-gray-300">
            {new Date(photo.taken_at).toLocaleDateString(undefined, {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </p>
        )}
        <p className="text-xs text-gray-400">
          {currentIndex + 1} / {photos.length}
        </p>
      </div>
    </div>
  );
}
