import { useQuery } from '@tanstack/react-query';
import { fetchPeople, fetchPerson, fetchPersonPhotos, fetchFaces } from '../api/faces';
import type { Person, PersonDetail, Face } from '../types/face';
import type { Photo } from '../types/photo';

export function usePeople(sort = 'face_count') {
  return useQuery<Person[]>({
    queryKey: ['people', sort],
    queryFn: () => fetchPeople(sort),
  });
}

export function usePerson(id: string | undefined) {
  return useQuery<PersonDetail>({
    queryKey: ['person', id],
    queryFn: () => fetchPerson(id!),
    enabled: !!id,
  });
}

export function usePersonPhotos(id: string | undefined, page = 1) {
  return useQuery<Photo[]>({
    queryKey: ['personPhotos', id, page],
    queryFn: () => fetchPersonPhotos(id!, { page, limit: 50 }),
    enabled: !!id,
  });
}

export function useFaces(params?: { person_id?: string; unassigned?: boolean }) {
  return useQuery<Face[]>({
    queryKey: ['faces', params],
    queryFn: () => fetchFaces(params),
  });
}

export function useFacesForPhoto(photoId: string | undefined) {
  return useQuery<Face[]>({
    queryKey: ['faces', 'photo', photoId],
    queryFn: () => fetchFaces({ photo_id: photoId }),
    enabled: !!photoId,
  });
}
