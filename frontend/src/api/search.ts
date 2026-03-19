import api from './client';
import type { Photo } from '../types/photo';
import type { PaginatedResponse } from '../types/api';

export interface SearchParams {
  q?: string;
  from_date?: string;
  to_date?: string;
  location?: string;
  person_id?: string;
  camera?: string;
  page?: number;
  limit?: number;
}

export async function searchPhotos(params: SearchParams): Promise<PaginatedResponse<Photo>> {
  const { data } = await api.get('/search', { params: { ...params, limit: params.limit ?? 50 } });
  return data;
}
