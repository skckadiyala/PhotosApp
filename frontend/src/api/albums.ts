import api from './client';

export async function fetchAlbums() {
  const { data } = await api.get('/albums');
  return data;
}

export async function fetchAlbum(id: string, params?: { cursor?: string; limit?: number }) {
  const { data } = await api.get(`/albums/${id}`, { params });
  return data;
}

export async function createAlbum(name: string, description?: string) {
  const { data } = await api.post('/albums', { name, description });
  return data;
}

export async function updateAlbum(albumId: string, updates: { name?: string; description?: string; cover_photo_id?: string | null }) {
  const { data } = await api.put(`/albums/${albumId}`, updates);
  return data;
}

export async function addPhotosToAlbum(albumId: string, photoIds: string[]) {
  const { data } = await api.post(`/albums/${albumId}/photos`, { photo_ids: photoIds });
  return data;
}
