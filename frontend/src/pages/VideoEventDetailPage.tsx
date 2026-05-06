import { useMemo, useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { format } from 'date-fns';
import { useEventClusterPhotos } from '../hooks/usePhotos';
import { useAuthStore } from '../stores/authStore';
import { useUIStore } from '../stores/uiStore';
import { VideoCard } from './VideosPage';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';

function parseClusterId(param?: string) {
  const value = param ? Number(param) : NaN;
  if (!Number.isInteger(value) || value < 1) return null;
  return value;
}

export default function VideoEventDetailPage() {
  const { clusterId: clusterParam } = useParams();
  const [searchParams] = useSearchParams();
  const accessToken = useAuthStore((s) => s.accessToken);
  const setPageHeader = useUIStore((s) => s.setPageHeader);

  const clusterId = parseClusterId(clusterParam);
  const gapHours = Number(searchParams.get('gap') ?? '6') || 6;

  const { data, isLoading } = useEventClusterPhotos(clusterId, gapHours, 'video');

  const heading = useMemo(() => {
    if (!data?.start_at) return `Event #${clusterId ?? '-'}`;
    return format(new Date(data.start_at), 'MMM d, yyyy • h:mm a');
  }, [data, clusterId]);

  useEffect(() => {
    if (data) setPageHeader(heading, `${data.count.toLocaleString()} videos`);
    return () => setPageHeader(null);
  }, [heading, data, setPageHeader]);

  if (clusterId === null) {
    return <EmptyState title="Invalid event" description="Please open an event folder from All Videos." />;
  }

  if (isLoading) return <Spinner />;

  if (!data || data.items.length === 0) {
    return <EmptyState title="Event not found" description="This event folder does not exist." />;
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.items.map((video) => (
        <VideoCard key={video.id} video={video} accessToken={accessToken} />
      ))}
    </div>
  );
}
