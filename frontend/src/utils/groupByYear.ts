import { format } from 'date-fns';
import type { Photo } from '../types/photo';

export interface MonthGroup {
  /** "yyyy-MM", e.g. "2024-03" */
  key: string;
  /** "MMMM yyyy", e.g. "March 2024" */
  label: string;
  year: number;
  month: number;
  photos: Photo[];
}

export interface YearGroup {
  year: number;
  /** Months sorted newest-first */
  months: MonthGroup[];
  /** First photo of the most recent month — used as year card cover */
  coverPhoto: Photo | null;
  count: number;
}

/**
 * Groups a flat array of photos into year → month hierarchy.
 * Both years and months within each year are sorted newest-first.
 * Photos without a taken_at date are placed in a separate "unknown" group
 * (excluded from years).
 */
export function groupByYearMonth(photos: Photo[]): YearGroup[] {
  const monthMap = new Map<string, MonthGroup>();

  for (const photo of photos) {
    const date = photo.taken_at ? new Date(photo.taken_at) : null;
    if (!date) continue; // skip undated photos in year/month views

    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const key = `${year}-${String(month).padStart(2, '0')}`;

    if (!monthMap.has(key)) {
      monthMap.set(key, {
        key,
        label: format(date, 'MMMM yyyy'),
        year,
        month,
        photos: [],
      });
    }
    monthMap.get(key)!.photos.push(photo);
  }

  // Aggregate into year groups
  const yearMap = new Map<number, YearGroup>();
  for (const mg of monthMap.values()) {
    if (!yearMap.has(mg.year)) {
      yearMap.set(mg.year, { year: mg.year, months: [], coverPhoto: null, count: 0 });
    }
    const yg = yearMap.get(mg.year)!;
    yg.months.push(mg);
    yg.count += mg.photos.length;
  }

  // Sort months newest-first, pick cover from newest month's first photo
  for (const yg of yearMap.values()) {
    yg.months.sort((a, b) => b.month - a.month);
    yg.coverPhoto = yg.months[0]?.photos[0] ?? null;
  }

  // Sort years newest-first
  return Array.from(yearMap.values()).sort((a, b) => b.year - a.year);
}
