import { useEffect, useMemo } from 'react';
import { useInView } from 'react-intersection-observer';
import { usePhotos } from '../hooks/usePhotos';
import { groupByMonth } from '../utils/groupByMonth';
import JustifiedPhotoGrid from '../components/photos/JustifiedPhotoGrid';
import { useScrollRestore } from '../hooks/useScrollRestore';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import type { Photo } from '../types/photo';

export default function PhotosPage() {
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = usePhotos('date_taken', 'image');
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

  useScrollRestore('photo', isLoading);

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
          <JustifiedPhotoGrid
            photos={group.photos}
            returnTo="/timeline"
            navPhotoIds={allPhotos.map((p) => p.id)}
          />
        </section>
      ))}

      {/* Infinite scroll sentinel */}
      <div ref={ref} className="h-10" />
      {isFetchingNextPage && <Spinner />}
    </div>
  );
}
