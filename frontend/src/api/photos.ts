import api from './client';
import type { Photo, PhotoDetail, LibrarySummary, MonthPhotosResponse } from '../types/photo';
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

export function getThumbnailUrl(photoId: string, size: 'sm' | 'md' | 'lg' = 'md') {
  const sizeMap = { sm: 'small', md: 'medium', lg: 'large' };
  return `/api/v1/photos/${photoId}/thumbnail?size=${sizeMap[size]}`;
}

export function getOriginalUrl(photoId: string) {
  return `/api/v1/photos/${photoId}/original`;
}

export function getVideoStreamUrl(photoId: string, token: string) {
  return `/api/v1/photos/${photoId}/stream?token=${encodeURIComponent(token)}`;
}

export async function fetchLibrarySummary(): Promise<LibrarySummary> {
  const { data } = await api.get<LibrarySummary>('/photos/library-summary');
  return data;
}

export async function fetchPhotosByMonth(year: number, month: number): Promise<MonthPhotosResponse> {
  const { data } = await api.get<MonthPhotosResponse>('/photos/by-month', {
    params: { year, month },
  });
  return data;
}
