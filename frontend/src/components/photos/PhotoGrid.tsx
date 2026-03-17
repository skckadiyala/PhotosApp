import type { Photo } from '../../types/photo';
import PhotoCard from './PhotoCard';

interface Props {
  photos: Photo[];
  onPhotoClick: (photo: Photo) => void;
}

export default function PhotoGrid({ photos, onPhotoClick }: Props) {
  return (
    <div className="grid grid-cols-2 gap-1 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
      {photos.map((photo) => (
        <PhotoCard key={photo.id} photo={photo} onClick={() => onPhotoClick(photo)} />
      ))}
    </div>
  );
}
