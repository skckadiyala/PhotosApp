import { useState } from 'react';
import type { Photo } from '../../types/photo';
import { getThumbnailUrl } from '../../api/photos';
import AuthImage from '../common/AuthImage';

interface Props {
  photo: Photo;
  onClick: () => void;
  /** Fills its parent container - used by the justified grid. */
  fill?: boolean;
}

export default function PhotoCard({ photo, onClick, fill = false }: Props) {
  const [loaded, setLoaded] = useState(false);

  return (
    <div
      className={`photo-grid-item relative cursor-pointer overflow-hidden bg-gray-200 ${
        fill ? 'h-full w-full' : 'aspect-square'
      }`}
      onClick={onClick}
    >
      {!loaded && (
        <div className="absolute inset-0 animate-pulse bg-gray-300" />
      )}

      <AuthImage
        src={getThumbnailUrl(photo.id, 'sm')}
        alt={photo.file_name}
        loading="lazy"
        onLoad={() => setLoaded(true)}
        className={`h-full w-full object-cover transition-opacity duration-300 ${
          loaded ? 'opacity-100' : 'opacity-0'
        }`}
      />

      {photo.is_favorite && (
        <div className="absolute bottom-1 right-1 text-red-500">
          <svg className="h-4 w-4 fill-current" viewBox="0 0 20 20">
            <path d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" />
          </svg>
        </div>
      )}
    </div>
  );
}
