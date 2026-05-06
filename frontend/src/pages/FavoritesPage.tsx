import { useNavigate } from 'react-router-dom';
import { useFavorites } from '../hooks/usePhotos';
import { useScrollRestore } from '../hooks/useScrollRestore';
import PhotoCard from '../components/photos/PhotoCard';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';

export default function FavoritesPage() {
  const navigate = useNavigate();
  const { data: favorites, isLoading } = useFavorites();

  useScrollRestore('photo', isLoading);

  if (isLoading) return <Spinner />;
  if (!favorites || favorites.length === 0)
    return <EmptyState title="No favorites" description="Mark photos as favorites to see them here" icon="❤️" />;

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-gray-900">Favorites</h1>
      <div className="grid grid-cols-3 gap-1 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
        {favorites.map((photo) => (
          <div key={photo.id} id={`photo-${photo.id}`}>
            <PhotoCard
              photo={photo}
              onClick={() =>
                navigate(`/photo/${photo.id}`, {
                  state: { photoIds: favorites.map((p) => p.id), returnTo: '/favorites' },
                })
              }
            />
          </div>
        ))}
      </div>
    </div>
  );
}
