import { useNavigate } from 'react-router-dom';
import PhotoCard from './PhotoCard';
import type { Photo } from '../../types/photo';
import { useUIStore } from '../../stores/uiStore';

interface Props {
  photos: Photo[];
  returnTo: string;
  rowHeight?: number;
  navPhotoIds?: string[];
}

export default function JustifiedPhotoGrid({ photos, returnTo, rowHeight = 180, navPhotoIds }: Props) {
  const navigate = useNavigate();
  const photoIds = navPhotoIds ?? photos.map((p) => p.id);

  const selectionMode = useUIStore((s) => s.selectionMode);
  const selectedPhotoIds = useUIStore((s) => s.selectedPhotoIds);
  const toggleSelect = useUIStore((s) => s.toggleSelect);

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
              selected={selectedPhotoIds.has(photo.id)}
              selectionMode={selectionMode}
              onSelect={() => toggleSelect(photo.id)}
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
