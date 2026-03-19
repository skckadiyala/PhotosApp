import { useNavigate } from 'react-router-dom';
import PhotoCard from './PhotoCard';
import type { Photo } from '../../types/photo';

interface Props {
  photos: Photo[];
  /** Route to pass as `returnTo` when navigating to PhotoDetailPage. */
  returnTo: string;
  /** Row height in pixels. Defaults to 180. */
  rowHeight?: number;
  /**
   * IDs to pass as navigation context. Defaults to the IDs of `photos`.
   * Override when the grid shows a subset (e.g. one month) but you want
   * prev/next to span the full photo list.
   */
  navPhotoIds?: string[];
}

/**
 * Google-Photos-style justified row layout.
 * Photos fill each row at a uniform height while preserving natural aspect ratios.
 * A large flexGrow spacer on the last "row" prevents it from stretching.
 */
export default function JustifiedPhotoGrid({ photos, returnTo, rowHeight = 180, navPhotoIds }: Props) {
  const navigate = useNavigate();
  const photoIds = navPhotoIds ?? photos.map((p) => p.id);

  return (
    <div className="flex flex-wrap" style={{ gap: '2px' }}>
      {photos.map((photo) => {
        const ratio = photo.width && photo.height ? photo.width / photo.height : 1;
        return (
          <div
            key={photo.id}
            id={`photo-${photo.id}`}
            style={{ flexGrow: 1, flexBasis: `${ratio * rowHeight}px`, height: `${rowHeight}px` }}
          >
            <PhotoCard
              photo={photo}
              fill
              onClick={() =>
                navigate(`/photo/${photo.id}`, {
                  state: { photoIds, returnTo },
                })
              }
            />
          </div>
        );
      })}
      {/* Absorb remaining space so the last row does not stretch */}
      <div style={{ flexGrow: 999 }} />
    </div>
  );
}
