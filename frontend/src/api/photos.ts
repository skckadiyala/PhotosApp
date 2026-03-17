import api from './client';

export async function triggerScan(): Promise<{ message: string; status: string }> {
  const { data } = await api.post('/scan');
  return data;
}

export async function rescanFaces(): Promise<{ message: string; status: string }> {
  const { data } = await api.post('/rescan-faces');
  return data;
}
import type { Photo, PhotoDetail } from '../types/photo';
import type { PaginatedResponse } from '../types/api';

export async function fetchPhotos(params: {
  page?: number;
  limit?: number;
  sort?: string;
}): Promise<PaginatedResponse<Photo>> {
  const { data } = await api.get('/photos', { params });
  return data;
}

export async function fetchPhoto(id: string): Promise<PhotoDetail> {
  const { data } = await api.get(`/photos/${id}`);
  return data;
}

export async function fetchPhotoMetadata(id: string) {
  const { data } = await api.get(`/photos/metadata/${id}`);
  return data;
}

export function getThumbnailUrl(photoId: string, size: 'sm' | 'md' | 'lg' = 'md') {
  const sizeMap = { sm: 'small', md: 'medium', lg: 'large' };
  return `/api/v1/photos/${photoId}/thumbnail?size=${sizeMap[size]}`;
}

export function getOriginalUrl(photoId: string) {
  return `/api/v1/photos/${photoId}/original`;
}
