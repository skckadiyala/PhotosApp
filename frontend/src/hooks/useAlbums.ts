import { useQuery } from '@tanstack/react-query';
import { fetchAlbums } from '../api/albums';

export function useAlbums() {
  return useQuery({
    queryKey: ['albums'],
    queryFn: fetchAlbums,
  });
}
