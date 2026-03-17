import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { fetchPhotos, fetchPhoto } from '../api/photos';

export function usePhotos(sort = 'date_taken') {
  return useInfiniteQuery({
    queryKey: ['photos', sort],
    queryFn: ({ pageParam = 1 }) => fetchPhotos({ page: pageParam, sort, limit: 50 }),
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
  });
}
