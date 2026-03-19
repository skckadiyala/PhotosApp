import { useInfiniteQuery } from '@tanstack/react-query';
import { searchPhotos } from '../api/search';
import type { SearchParams } from '../api/search';

export function useSearch(params: Omit<SearchParams, 'page' | 'limit'>) {
  return useInfiniteQuery({
    queryKey: ['search', params],
    queryFn: ({ pageParam = 1 }) => searchPhotos({ ...params, page: pageParam, limit: 100 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
    enabled: Boolean(params.q || params.person_id || params.from_date || params.to_date || params.location),
  });
}
