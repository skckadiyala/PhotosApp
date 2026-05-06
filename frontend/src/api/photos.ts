import api from './client';
import type {
  Photo,
  PhotoDetail,
  LibrarySummary,
  MonthPhotosResponse,
  EventClusterSummary,
  EventClusterPhotosResponse,
} from '../types/photo';
import type { PaginatedResponse } from '../types/api';

export async function triggerScan(): Promise<{ message: string; status: string }> {
  const { data } = await api.post('/scan');
  return data;
}

export async function rescanFaces(): Promise<{ message: string; status: string }> {
  const { data } = await api.post('/rescan-faces');
  return data;
}

export async function scanPhotoFaces(photoId: string): Promise<{ message: string; status: string }> {
  const { data } = await api.post(`/photos/${photoId}/scan-faces`);
  return data;
}

export async function addManualFace(
  photoId: string,
  region: { top: number; right: number; bottom: number; left: number },
): Promise<{ message: string; status: string }> {
  const { data } = await api.post(`/photos/${photoId}/faces/manual`, region);
  return data;
}

export async function toggleFavorite(photoId: string, favorite: boolean): Promise<void> {
  if (favorite) {
    await api.post(`/favorites/${photoId}`);
  } else {
    await api.delete(`/favorites/${photoId}`);
  }
}

export async function fetchPhotos(params: {
  page?: number;
  limit?: number;
  sort?: string;
  media_type?: string;
}): Promise<PaginatedResponse<Photo>> {
  const { data } = await api.get('/photos', { params });
  return data;
}

export async function fetchPhoto(id: string): Promise<PhotoDetail> {
  const { data } = await api.get(`/photos/${id}`);
  return data;
}

export function getThumbnailUrl(photoId: string, size: 'sm' | 'md' | 'lg' = 'md', thumbPath?: string | null) {
  if (thumbPath) return `/thumbnails/${thumbPath}`;
  const sizeMap = { sm: 'small', md: 'medium', lg: 'large' };
  return `/api/v1/photos/${photoId}/thumbnail?size=${sizeMap[size]}`;
}

export function getOriginalUrl(photoId: string) {
  return `/api/v1/photos/${photoId}/original`;
}

export function getVideoStreamUrl(photoId: string, token: string) {
  return `/api/v1/photos/${photoId}/stream?token=${encodeURIComponent(token)}`;
}

export async function fetchLibrarySummary(mediaType: string = 'image'): Promise<LibrarySummary> {
  const { data } = await api.get<LibrarySummary>('/photos/library-summary', {
    params: { media_type: mediaType },
  });
  return data;
}

export async function fetchPhotosByMonth(
  year: number,
  month: number,
  mediaType: string = 'image',
): Promise<MonthPhotosResponse> {
  const { data } = await api.get<MonthPhotosResponse>('/photos/by-month', {
    params: { year, month, media_type: mediaType },
  });
  return data;
}

export async function fetchEventClusters(params: {
  page?: number;
  limit?: number;
  gap_hours?: number;
  media_type?: string;
}): Promise<PaginatedResponse<EventClusterSummary>> {
  const { data } = await api.get<PaginatedResponse<EventClusterSummary>>('/photos/event-clusters', { params });
  return data;
}

export async function fetchEventClusterPhotos(
  clusterId: number,
  gapHours: number = 6,
  mediaType: string = 'image',
): Promise<EventClusterPhotosResponse> {
  const { data } = await api.get<EventClusterPhotosResponse>(`/photos/event-clusters/${clusterId}`, {
    params: { gap_hours: gapHours, media_type: mediaType },
  });
  return data;
}

export async function archivePhotos(
  photoIds: string[],
): Promise<{ archived: string[]; errors: { id: string; error: string }[] }> {
  const { data } = await api.post('/photos/archive', { photo_ids: photoIds });
  return data;
}

export async function fetchFavorites(): Promise<{ items: Photo[] }> {
  const { data } = await api.get<{ items: Photo[] }>('/favorites');
  return data;
}
