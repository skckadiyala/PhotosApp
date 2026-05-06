import type { Photo } from '../../types/photo';

interface Props {
  photo: Photo;
  onClick: () => void;
  fill?: boolean;
  selected?: boolean;
  selectionMode?: boolean;
  onSelect?: () => void;
}

export default function PhotoCard({
  photo,
  onClick,
  fill = false,
  selected = false,
  selectionMode = false,
  onSelect,
}: Props) {
  const handleClick = () => {
    if (selectionMode) { onSelect?.(); return; }
    onClick();
  };

  return (
    <div
      className={`photo-grid-item group relative cursor-pointer overflow-hidden bg-gray-200 ${fill ? 'h-full w-full' : 'aspect-square'}`}
      onClick={handleClick}
    >
      {photo.thumb_md || photo.thumb_sm ? (
        <img
          src={`/thumbnails/${photo.thumb_md ?? photo.thumb_sm}`}
          alt={photo.file_name}
          loading="lazy"
          decoding="async"
          className={`h-full w-full object-cover transition-opacity duration-300 ${selected ? 'scale-95 brightness-75' : ''}`}
        />
      ) : (
        <div className="h-full w-full bg-gray-300 animate-pulse" />
      )}
      {selected && <div className="absolute inset-0 bg-blue-500/20 pointer-events-none" />}
      {selected && <div className="absolute inset-0 ring-2 ring-inset ring-blue-500 pointer-events-none rounded-sm" />}

      {selectionMode && (
        <button
          className="absolute left-2 top-2 z-10"
          onClick={(e) => { e.stopPropagation(); onSelect?.(); }}
          aria-label={selected ? 'Deselect photo' : 'Select photo'}
        >
          <div className={`flex h-6 w-6 items-center justify-center rounded-full border-2 transition-colors ${selected ? 'border-blue-500 bg-blue-500' : 'border-white bg-white/70 shadow'}`}>
            {selected && (
              <svg className="h-3.5 w-3.5 text-white" viewBox="0 0 24 24" fill="none">
                <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
        </button>
      )}

      {photo.is_favorite && !selectionMode && (
        <div className="absolute bottom-1 right-1 text-red-500">
          <svg className="h-4 w-4 fill-current" viewBox="0 0 20 20">
            <path d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" />
          </svg>
        </div>
      )}
    </div>
  );
}
