import api from './client';
import type { Person, PersonDetail, Face } from '../types/face';
import type { Photo } from '../types/photo';

export function getFaceThumbnailUrl(faceId: string, size: number = 200) {
  return `/api/v1/faces/${faceId}/thumbnail?size=${size}`;
}

export async function fetchPeople(sort?: string): Promise<Person[]> {
  const { data } = await api.get('/people', { params: { sort } });
  return data;
}

export async function fetchPerson(id: string): Promise<PersonDetail> {
  const { data } = await api.get(`/people/${id}`);
  return data;
}

export async function fetchPersonPhotos(id: string, params?: { page?: number; limit?: number }): Promise<Photo[]> {
  const { data } = await api.get(`/people/${id}/photos`, { params });
  return data;
}

export async function renamePerson(id: string, name: string): Promise<Person> {
  const { data } = await api.post(`/people/${id}/name`, { name });
  return data;
}

export async function fetchFaces(params?: { photo_id?: string; person_id?: string; unassigned?: boolean; limit?: number }): Promise<Face[]> {
  const { data } = await api.get('/faces', { params });
  return data;
}

export async function assignFace(faceId: string, body: { person_id?: string; new_person_name?: string }) {
  const { data } = await api.put(`/faces/${faceId}/assign`, body);
  return data;
}

export async function deleteFace(faceId: string): Promise<{ message: string }> {
  const { data } = await api.delete(`/faces/${faceId}`);
  return data;
}

export async function mergePeople(targetId: string, sourceIds: string[]): Promise<Person> {
  const { data } = await api.post(`/people/${targetId}/merge`, { source_ids: sourceIds });
  return data;
}

// ---------- Face confirmation ----------

export interface FaceConfirmItem {
  id: string;
  photo_id: string;
  person_id: string | null;
  person_name: string | null;
  match_distance: number;
  status: string;
  confidence: number;
  bbox_top: number;
  bbox_right: number;
  bbox_bottom: number;
  bbox_left: number;
  reference_face_id: string | null;
  created_at: string | null;
}

export async function fetchFacesToConfirm(limit = 50): Promise<FaceConfirmItem[]> {
  const { data } = await api.get('/faces/confirm', { params: { limit } });
  return data;
}

export async function confirmFace(faceId: string, accept: boolean) {
  const { data } = await api.post(`/faces/${faceId}/confirm`, null, { params: { accept } });
  return data;
}

export async function fetchConfirmCount(): Promise<number> {
  const { data } = await api.get('/faces/confirm/count');
  return data.count;
}
