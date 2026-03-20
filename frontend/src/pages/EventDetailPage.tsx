import { useMemo } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { format } from 'date-fns';
import { useEventClusterPhotos } from '../hooks/usePhotos';
import JustifiedPhotoGrid from '../components/photos/JustifiedPhotoGrid';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import { useScrollRestore } from '../hooks/useScrollRestore';

function parseClusterId(param?: string) {
  const value = param ? Number(param) : NaN;
  if (!Number.isInteger(value) || value < 1) return null;
  return value;
}

export default function EventDetailPage() {
  const { clusterId: clusterParam } = useParams();
  const [searchParams] = useSearchParams();

  const clusterId = parseClusterId(clusterParam);
  const gapHours = Number(searchParams.get('gap') ?? '6') || 6;

  const { data, isLoading } = useEventClusterPhotos(clusterId, gapHours);

  useScrollRestore('photo', isLoading);

  const heading = useMemo(() => {
    if (!data?.start_at) return `Event #${clusterId ?? '-'}`;
    return format(new Date(data.start_at), 'MMM d, yyyy • h:mm a');
  }, [data, clusterId]);

  if (clusterId === null) {
    return <EmptyState title="Invalid event" description="Please open an event folder from All Photos." />;
  }

  if (isLoading) return <Spinner />;

  if (!data || data.items.length === 0) {
    return <EmptyState title="Event not found" description="This event folder does not exist." />;
  }

  return (
    <div className="space-y-6">
      <div className="sticky top-0 z-20 -mx-4 border-b border-gray-100 bg-white/95 px-4 py-3 backdrop-blur-sm grid items-center gap-3"
        style={{ gridTemplateColumns: '1fr auto 1fr' }}
      >
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{heading}</h1>
          <p className="text-sm text-gray-500">{data.count.toLocaleString()} photos</p>
        </div>

        <div className="flex items-center gap-0.5 rounded-lg bg-gray-100 p-1">
          <Link to="/library?view=years" className="rounded-md px-4 py-1.5 text-sm font-medium text-gray-500 hover:text-gray-700">
            Years
          </Link>
          <Link to="/library?view=months" className="rounded-md px-4 py-1.5 text-sm font-medium text-gray-500 hover:text-gray-700">
            Months
          </Link>
          <Link to="/library?view=all" className="rounded-md bg-white px-4 py-1.5 text-sm font-medium text-gray-900 shadow-sm">
            All Photos
          </Link>
        </div>

        <div className="flex justify-end">
          <Link
            to={`/library?view=all`}
            className="text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            Back to All Photos
          </Link>
        </div>
      </div>

      <JustifiedPhotoGrid
        photos={data.items}
        returnTo={`/library/event/${clusterId}?gap=${gapHours}`}
        navPhotoIds={data.items.map((p) => p.id)}
      />
    </div>
  );
}
