import { useEffect, useMemo } from 'react';
import { useInView } from 'react-intersection-observer';
import { useNavigate } from 'react-router-dom';
import { format } from 'date-fns';
import { usePhotos } from '../hooks/usePhotos';
import PhotoCard from '../components/photos/PhotoCard';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import type { Photo } from '../types/photo';

interface PhotoGroup {
  label: string;
  photos: Photo[];
}

function groupByMonth(photos: Photo[]): PhotoGroup[] {
  const groups = new Map<string, Photo[]>();
  for (const photo of photos) {
    const date = photo.taken_at ? new Date(photo.taken_at) : null;
    const label = date ? format(date, 'MMMM yyyy') : 'Unknown Date';
    const existing = groups.get(label);
    if (existing) {
      existing.push(photo);
    } else {
      groups.set(label, [photo]);
    }
  }
  return Array.from(groups.entries()).map(([label, photos]) => ({ label, photos }));
}

export default function PhotosPage() {
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = usePhotos();
  const navigate = useNavigate();
  const { ref, inView } = useInView();

  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const allPhotos: Photo[] = useMemo(
    () => data?.pages.flatMap((page) => page.items) ?? [],
    [data],
  );

  const groups = useMemo(() => groupByMonth(allPhotos), [allPhotos]);

  if (isLoading) return <Spinner />;
  if (allPhotos.length === 0)
    return <EmptyState title="No photos yet" description="Add photos to your library to get started" />;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold text-gray-900">Timeline</h1>

      {groups.map((group) => (
        <section key={group.label}>
          <h2 className="mb-3 text-lg font-medium text-gray-700 sticky top-0 bg-gray-50 py-2 z-10">
            {group.label}
          </h2>
          <div className="grid grid-cols-3 gap-1 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
            {group.photos.map((photo) => (
              <PhotoCard
                key={photo.id}
                photo={photo}
                onClick={() => navigate(`/photo/${photo.id}`)}
              />
            ))}
          </div>
        </section>
      ))}

      {/* Infinite scroll sentinel */}
      <div ref={ref} className="h-10" />
      {isFetchingNextPage && <Spinner />}
    </div>
  );
}
