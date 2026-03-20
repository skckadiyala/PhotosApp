import { format } from 'date-fns';
import type { Photo } from '../types/photo';

export interface TimeGroup {
  key: string;
  label: string;
  photos: Photo[];
}

export interface EventCluster {
  key: string;
  title: string;
  subtitle: string;
  marker: string;
  photos: Photo[];
  groups: TimeGroup[];
}

const THREE_HOURS_MS = 3 * 60 * 60 * 1000;
const TWENTY_FOUR_HOURS_MS = 24 * 60 * 60 * 1000;

function getPhotoTimestamp(photo: Photo): number {
  const value = photo.taken_at ?? null;
  if (!value) return 0;
  const ts = new Date(value).getTime();
  return Number.isFinite(ts) ? ts : 0;
}

function buildTimeGroups(photos: Photo[], baseKey: string): TimeGroup[] {
  if (photos.length === 0) return [];

  const sorted = [...photos].sort((a, b) => getPhotoTimestamp(b) - getPhotoTimestamp(a));
  const groups: TimeGroup[] = [];
  let current: Photo[] = [sorted[0]];

  for (let i = 1; i < sorted.length; i += 1) {
    const prevTs = getPhotoTimestamp(sorted[i - 1]);
    const nextTs = getPhotoTimestamp(sorted[i]);
    const gap = Math.abs(prevTs - nextTs);

    if (gap <= THREE_HOURS_MS) {
      current.push(sorted[i]);
    } else {
      const topTs = getPhotoTimestamp(current[0]);
      const label = topTs > 0 ? format(new Date(topTs), 'EEE, MMM d • h:mm a') : 'Unknown time';
      groups.push({
        key: `${baseKey}-group-${groups.length}`,
        label,
        photos: current,
      });
      current = [sorted[i]];
    }
  }

  if (current.length > 0) {
    const topTs = getPhotoTimestamp(current[0]);
    const label = topTs > 0 ? format(new Date(topTs), 'EEE, MMM d • h:mm a') : 'Unknown time';
    groups.push({
      key: `${baseKey}-group-${groups.length}`,
      label,
      photos: current,
    });
  }

  return groups;
}

export function groupByAdaptiveClusters(photos: Photo[]): EventCluster[] {
  if (photos.length === 0) return [];

  const sorted = [...photos].sort((a, b) => getPhotoTimestamp(b) - getPhotoTimestamp(a));

  const clusterBuckets: Photo[][] = [];
  let currentCluster: Photo[] = [sorted[0]];

  for (let i = 1; i < sorted.length; i += 1) {
    const prevTs = getPhotoTimestamp(sorted[i - 1]);
    const nextTs = getPhotoTimestamp(sorted[i]);
    const gap = Math.abs(prevTs - nextTs);

    if (gap > TWENTY_FOUR_HOURS_MS) {
      clusterBuckets.push(currentCluster);
      currentCluster = [sorted[i]];
    } else {
      currentCluster.push(sorted[i]);
    }
  }

  if (currentCluster.length > 0) {
    clusterBuckets.push(currentCluster);
  }

  return clusterBuckets.map((bucket, idx) => {
    const startTs = getPhotoTimestamp(bucket[0]);
    const endTs = getPhotoTimestamp(bucket[bucket.length - 1]);

    const hasDates = startTs > 0 && endTs > 0;
    const title = hasDates
      ? format(new Date(startTs), 'MMM d, yyyy')
      : `Event ${idx + 1}`;

    const subtitle = hasDates
      ? `${format(new Date(endTs), 'MMM d')} • ${bucket.length.toLocaleString()} photos`
      : `${bucket.length.toLocaleString()} photos`;

    const marker = hasDates
      ? format(new Date(startTs), 'MMM d')
      : `E${idx + 1}`;

    const key = hasDates
      ? `event-${format(new Date(startTs), 'yyyy-MM-dd-HH-mm')}-${idx}`
      : `event-unknown-${idx}`;

    return {
      key,
      title,
      subtitle,
      marker,
      photos: bucket,
      groups: buildTimeGroups(bucket, key),
    };
  });
}
