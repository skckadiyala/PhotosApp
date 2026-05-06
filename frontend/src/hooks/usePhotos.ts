import { useInfiniteQuery, useQuery, keepPreviousData } from '@tanstack/react-query';
import {
  fetchPhotos,
  fetchPhoto,
  fetchFavorites,
  fetchLibrarySummary,
  fetchPhotosByMonth,
  fetchEventClusters,
  fetchEventClusterPhotos,
} from '../api/photos';
import type { Photo, LibrarySummary, MonthPhotosResponse, EventClusterPhotosResponse } from '../types/photo';

export function useFavorites() {
  return useQuery<Photo[]>({
    queryKey: ['favorites'],
    queryFn: async () => {
      const res = await fetchFavorites();
      return res.items;
    },
    staleTime: 60 * 1000,
  });
}

export function usePhotos(sort = 'date_taken', media_type?: string) {
  return useInfiniteQuery({
    queryKey: ['photos', sort, media_type],
    queryFn: ({ pageParam = 1 }) => fetchPhotos({ page: pageParam, sort, limit: 50, media_type }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
    staleTime: 2 * 60 * 1000,  // 2 minutes — prevents refetch on every navigation
  });
}

export function useLibrarySummary(mediaType: string = 'image') {
  return useQuery<LibrarySummary>({
    queryKey: ['library-summary', mediaType],
    queryFn: () => fetchLibrarySummary(mediaType),
    staleTime: 5 * 60 * 1000,  // 5 minutes — single DB query replaces 2000+ page fetches
  });
}

export function usePhoto(id: string | undefined) {
  return useQuery({
    queryKey: ['photo', id],
    queryFn: () => fetchPhoto(id!),
    enabled: !!id,
    staleTime: 10 * 60 * 1000,  // 10 min — photo metadata rarely changes; avoids re-fetch on back-navigation
    placeholderData: keepPreviousData,
  });
}

export function usePhotosByMonth(year: number | null, month: number | null, mediaType: string = 'image') {
  return useQuery<MonthPhotosResponse>({
    queryKey: ['photos-by-month', year, month, mediaType],
    queryFn: () => fetchPhotosByMonth(year!, month!, mediaType),
    enabled: year !== null && month !== null,
    staleTime: 5 * 60 * 1000,
  });
}

export function useEventClusters(gapHours: number = 6, mediaType: string = 'image') {
  return useInfiniteQuery({
    queryKey: ['event-clusters', gapHours, mediaType],
    queryFn: ({ pageParam = 1 }) => fetchEventClusters({ page: pageParam, limit: 50, gap_hours: gapHours, media_type: mediaType }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
    staleTime: 5 * 60 * 1000,
  });
}

export function useEventClusterPhotos(clusterId: number | null, gapHours: number = 6, mediaType: string = 'image') {
  return useQuery<EventClusterPhotosResponse>({
    queryKey: ['event-cluster-photos', clusterId, gapHours, mediaType],
    queryFn: () => fetchEventClusterPhotos(clusterId!, gapHours, mediaType),
    enabled: clusterId !== null,
    staleTime: 5 * 60 * 1000,
  });
}
