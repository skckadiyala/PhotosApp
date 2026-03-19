import { format } from 'date-fns';
import type { Photo } from '../types/photo';

export interface PhotoGroup {
  /** "MMMM yyyy" label, e.g. "March 2024" */
  label: string;
  /** "yyyy-MM" key used for section IDs and scroll targeting, e.g. "2024-03" */
  key: string;
  photos: Photo[];
}

export function groupByMonth(photos: Photo[]): PhotoGroup[] {
  const groups = new Map<string, { label: string; photos: Photo[] }>();
  for (const photo of photos) {
    const date = photo.taken_at ? new Date(photo.taken_at) : null;
    const key = date ? format(date, 'yyyy-MM') : 'unknown';
    const label = date ? format(date, 'MMMM yyyy') : 'Unknown Date';
    const existing = groups.get(key);
    if (existing) existing.photos.push(photo);
    else groups.set(key, { label, photos: [photo] });
  }
  return Array.from(groups.entries()).map(([key, { label, photos }]) => ({ key, label, photos }));
}
