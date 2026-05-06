import { useMemo, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { format } from 'date-fns';
import { usePhotosByMonth } from '../hooks/usePhotos';
import { useAuthStore } from '../stores/authStore';
import { useUIStore } from '../stores/uiStore';
import { VideoCard } from './VideosPage';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';

function parseMonthParams(yearParam?: string, monthParam?: string) {
  const year = yearParam ? Number(yearParam) : NaN;
  const month = monthParam ? Number(monthParam) : NaN;
  if (!Number.isInteger(year) || year < 1900 || year > 2200) return { year: null, month: null };
  if (!Number.isInteger(month) || month < 1 || month > 12) return { year: null, month: null };
  return { year, month };
}

export default function VideoMonthDetailPage() {
  const { year: yearParam, month: monthParam } = useParams();
  const { year, month } = parseMonthParams(yearParam, monthParam);
  const accessToken = useAuthStore((s) => s.accessToken);
  const setPageHeader = useUIStore((s) => s.setPageHeader);

  const { data, isLoading } = usePhotosByMonth(year, month, 'video');

  const heading = useMemo(() => {
    if (year === null || month === null) return 'Invalid month';
    return format(new Date(year, month - 1, 1), 'MMMM yyyy');
  }, [year, month]);

  useEffect(() => {
    if (data) setPageHeader(heading, `${data.count.toLocaleString()} videos`);
    return () => setPageHeader(null);
  }, [heading, data, setPageHeader]);

  if (year === null || month === null) {
    return <EmptyState title="Invalid month" description="Please select a valid month from Videos > Months." />;
  }

  if (isLoading) return <Spinner />;

  if (!data || data.items.length === 0) {
    return <EmptyState title={heading} description="No videos found for this month." icon="🎬" />;
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.items.map((video) => (
        <VideoCard key={video.id} video={video} accessToken={accessToken} />
      ))}
    </div>
  );
}
