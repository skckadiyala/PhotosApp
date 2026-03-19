import { format } from 'date-fns';
import type { Photo } from '../types/photo';

export interface PhotoGroup {
  label: string;
  photos: Photo[];
}

export function groupByMonth(photos: Photo[]): PhotoGroup[] {
  const groups = new Map<string, Photo[]>();
  for (const photo of photos) {
    const date = photo.taken_at ? new Date(photo.taken_at) : null;
    const label = date ? format(date, 'MMMM yyyy') : 'Unknown Date';
    const existing = groups.get(label);
    if (existing) existing.push(photo);
    else groups.set(label, [photo]);
  }
  return Array.from(groups.entries()).map(([label, photos]) => ({ label, photos }));
}
