import { useEffect, useMemo, useState } from 'react';
import { useInView } from 'react-intersection-observer';
import { format } from 'date-fns';
import { usePhotos } from '../hooks/usePhotos';
import { groupByMonth } from '../utils/groupByMonth';
import { useScrollRestore } from '../hooks/useScrollRestore';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import { getVideoStreamUrl, getThumbnailUrl } from '../api/photos';
import { useAuthStore } from '../stores/authStore';
import type { Photo } from '../types/photo';

function formatBytes(bytes: number): string {
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
}

function formatDuration(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}


function VideoCard({ video, accessToken }: { video: Photo; accessToken: string | null }) {
  const [duration, setDuration] = useState<number | null>(null);

  return (
    <div id={`video-${video.id}`} className="rounded-xl overflow-hidden bg-gray-900 shadow flex flex-col">
      <video
        src={accessToken ? getVideoStreamUrl(video.id, accessToken) : undefined}
        poster={video.thumb_md ? getThumbnailUrl(video.id, 'md') : undefined}
        controls
        preload="metadata"
        className="w-full aspect-video object-contain bg-black"
        onLoadedMetadata={(e) => setDuration((e.target as HTMLVideoElement).duration)}
      />
      <div className="px-3 py-2.5 space-y-1">
        <p className="truncate text-sm font-medium text-gray-100" title={video.file_name}>
          {video.file_name}
        </p>
        <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-gray-400">
          {video.taken_at ? (
            <span>{format(new Date(video.taken_at), 'MMM d, yyyy · h:mm a')}</span>
          ) : (
            <span className="text-gray-600">Date unknown</span>
          )}
          {duration !== null && (
            <span className="flex items-center gap-0.5">
              <svg className="w-3 h-3" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
              </svg>
              {formatDuration(duration)}
            </span>
          )}
          {video.file_size != null && (
            <span>{formatBytes(video.file_size)}</span>
          )}
          {video.width != null && video.height != null && (
            <span>{video.width}×{video.height}</span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VideosPage() {
  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = usePhotos('date_taken', 'video');
  const accessToken = useAuthStore((s) => s.accessToken);
  const { ref, inView } = useInView();

  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) fetchNextPage();
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const allVideos: Photo[] = useMemo(
    () => data?.pages.flatMap((p) => p.items) ?? [],
    [data],
  );

  const groups = useMemo(() => groupByMonth(allVideos), [allVideos]);

  useScrollRestore('video', isLoading);

  if (isLoading) return <Spinner />;
  if (allVideos.length === 0)
    return <EmptyState title="No videos" description="Videos from your library will appear here" icon="🎬" />;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold text-gray-900">Videos ({allVideos.length})</h1>

      {groups.map((group) => (
        <section key={group.label}>
          <h2 className="mb-3 text-lg font-medium text-gray-700 sticky top-0 bg-gray-50 py-2 z-10">
            {group.label}
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {group.photos.map((video) => (
              <VideoCard key={video.id} video={video} accessToken={accessToken} />
            ))}
          </div>
        </section>
      ))}

      <div ref={ref} className="h-10" />
      {isFetchingNextPage && <Spinner />}
    </div>
  );
}
