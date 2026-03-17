import api from './client';

// ── Types ───────────────────────────────────────────────────

export interface MapCluster {
  lat: number;
  lng: number;
  count: number;
  preview_photo_id: string;
  location_label: string | null;
}

export interface MapPhoto {
  id: string;
  file_name: string;
  thumb_sm: string | null;
  lat: number;
  lng: number;
  location_label: string | null;
}

export interface LocationItem {
  id: string;
  city: string | null;
  state: string | null;
  country: string | null;
  formatted: string | null;
  latitude: number;
  longitude: number;
  photo_count: number;
}

// ── API calls ───────────────────────────────────────────────

export async function fetchMapClusters(
  zoom: number,
  bounds?: { sw_lat: number; sw_lng: number; ne_lat: number; ne_lng: number },
): Promise<MapCluster[]> {
  const params: Record<string, number> = { zoom };
  if (bounds) {
    params.sw_lat = bounds.sw_lat;
    params.sw_lng = bounds.sw_lng;
    params.ne_lat = bounds.ne_lat;
    params.ne_lng = bounds.ne_lng;
  }
  const { data } = await api.get('/map/clusters', { params });
  return data.clusters;
}

export async function fetchMapPhotos(
  lat: number,
  lng: number,
  radius = 50,
  limit = 50,
): Promise<MapPhoto[]> {
  const { data } = await api.get('/map/photos', { params: { lat, lng, radius, limit } });
  return data.items;
}

export async function fetchLocations(): Promise<LocationItem[]> {
  const { data } = await api.get('/map/locations');
  return data.items;
}
