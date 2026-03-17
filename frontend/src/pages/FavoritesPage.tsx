import { useNavigate } from 'react-router-dom';
import { usePhotos } from '../hooks/usePhotos';
import PhotoCard from '../components/photos/PhotoCard';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import type { Photo } from '../types/photo';

export default function FavoritesPage() {
  const navigate = useNavigate();
  // Use the main photos query and filter favorites client-side
  const { data, isLoading } = usePhotos();

  const allPhotos: Photo[] = data?.pages.flatMap((page) => page.items) ?? [];
  const favorites = allPhotos.filter((p) => p.is_favorite);

  if (isLoading) return <Spinner />;
  if (favorites.length === 0)
    return <EmptyState title="No favorites" description="Mark photos as favorites to see them here" icon="❤️" />;

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-gray-900">Favorites</h1>
      <div className="grid grid-cols-3 gap-1 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
        {favorites.map((photo) => (
          <PhotoCard
            key={photo.id}
            photo={photo}
            onClick={() => navigate(`/photo/${photo.id}`)}
          />
        ))}
      </div>
    </div>
  );
}
