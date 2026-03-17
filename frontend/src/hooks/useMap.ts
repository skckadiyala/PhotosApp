import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { fetchMapClusters, fetchMapPhotos, fetchLocations } from '../api/map';
import type { MapCluster, MapPhoto, LocationItem } from '../api/map';

export function useMapClusters(zoom: number, bounds?: { sw_lat: number; sw_lng: number; ne_lat: number; ne_lng: number }) {
  return useQuery<MapCluster[]>({
    queryKey: ['mapClusters', zoom, bounds],
    queryFn: () => fetchMapClusters(zoom, bounds),
    staleTime: 30_000,
    // Keep previous cluster markers visible while new data loads so markers
    // never all disappear at once — the main cause of frame-to-frame jumping.
    placeholderData: keepPreviousData,
  });
}

export function useMapPhotos(lat: number, lng: number, radius = 50) {
  return useQuery<MapPhoto[]>({
    queryKey: ['mapPhotos', lat, lng, radius],
    queryFn: () => fetchMapPhotos(lat, lng, radius),
    enabled: lat !== 0 || lng !== 0,
    staleTime: 30_000,
  });
}

export function useLocations() {
  return useQuery<LocationItem[]>({
    queryKey: ['locations'],
    queryFn: fetchLocations,
  });
}
