import { useInfiniteQuery, useQuery, keepPreviousData } from '@tanstack/react-query';
import {
  fetchPhotos,
  fetchPhoto,
  fetchLibrarySummary,
  fetchPhotosByMonth,
  fetchEventClusters,
  fetchEventClusterPhotos,
} from '../api/photos';
import type { LibrarySummary, MonthPhotosResponse, EventClusterPhotosResponse } from '../types/photo';

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

export function useLibrarySummary() {
  return useQuery<LibrarySummary>({
    queryKey: ['library-summary'],
    queryFn: fetchLibrarySummary,
    staleTime: 5 * 60 * 1000,  // 5 minutes — single DB query replaces 2000+ page fetches
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

export function usePhotosByMonth(year: number | null, month: number | null) {
  return useQuery<MonthPhotosResponse>({
    queryKey: ['photos-by-month', year, month],
    queryFn: () => fetchPhotosByMonth(year!, month!),
    enabled: year !== null && month !== null,
    staleTime: 5 * 60 * 1000,
  });
}

export function useEventClusters(gapHours: number = 6) {
  return useInfiniteQuery({
    queryKey: ['event-clusters', gapHours],
    queryFn: ({ pageParam = 1 }) => fetchEventClusters({ page: pageParam, limit: 50, gap_hours: gapHours }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
    staleTime: 5 * 60 * 1000,
  });
}

export function useEventClusterPhotos(clusterId: number | null, gapHours: number = 6) {
  return useQuery<EventClusterPhotosResponse>({
    queryKey: ['event-cluster-photos', clusterId, gapHours],
    queryFn: () => fetchEventClusterPhotos(clusterId!, gapHours),
    enabled: clusterId !== null,
    staleTime: 5 * 60 * 1000,
  });
}
