import { useInfiniteQuery, useQuery, keepPreviousData } from '@tanstack/react-query';
import { fetchPhotos, fetchPhoto } from '../api/photos';

export function usePhotos(sort = 'date_taken', media_type?: string) {
  return useInfiniteQuery({
    queryKey: ['photos', sort, media_type],
    queryFn: ({ pageParam = 1 }) => fetchPhotos({ page: pageParam, sort, limit: 50, media_type }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
  });
}

export function usePhoto(id: string | undefined) {
  return useQuery({
    queryKey: ['photo', id],
    queryFn: () => fetchPhoto(id!),
    enabled: !!id,
    // Keep showing the previous photo while the next one loads — prevents
    // the grid page from bleeding through during inter-photo navigation.
    placeholderData: keepPreviousData,
  });
}
