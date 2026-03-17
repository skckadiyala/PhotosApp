import api from './client';
import type { Photo } from '../types/photo';
import type { PaginatedResponse } from '../types/api';

export interface SearchParams {
  q?: string;
  from_date?: string;
  to_date?: string;
  person_id?: string;
  camera?: string;
  page?: number;
  limit?: number;
}

// Search uses the photos endpoint with sorting — backend doesn't have a dedicated search endpoint
// For full-text we filter client-side or extend later
export async function searchPhotos(params: SearchParams): Promise<PaginatedResponse<Photo>> {
  const { data } = await api.get('/photos', {
    params: { page: params.page || 1, limit: params.limit || 50, sort: 'date_taken' },
  });
  return data;
}
