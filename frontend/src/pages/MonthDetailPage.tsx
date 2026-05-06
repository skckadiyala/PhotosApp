import { useMemo, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useUIStore } from '../stores/uiStore';
import { format } from 'date-fns';
import { usePhotosByMonth } from '../hooks/usePhotos';
import JustifiedPhotoGrid from '../components/photos/JustifiedPhotoGrid';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import { useScrollRestore } from '../hooks/useScrollRestore';
import { groupByAdaptiveClusters } from '../utils/groupByAdaptiveClusters';
import EventScrollScrubber from '../components/photos/EventScrollScrubber';

function parseMonthParams(yearParam?: string, monthParam?: string) {
  const year = yearParam ? Number(yearParam) : NaN;
  const month = monthParam ? Number(monthParam) : NaN;

  if (!Number.isInteger(year) || year < 1900 || year > 2200) return { year: null, month: null };
  if (!Number.isInteger(month) || month < 1 || month > 12) return { year: null, month: null };

  return { year, month };
}

export default function MonthDetailPage() {
  const { year: yearParam, month: monthParam } = useParams();
  const { year, month } = parseMonthParams(yearParam, monthParam);
  const setPageHeader = useUIStore((s) => s.setPageHeader);

  const { data, isLoading } = usePhotosByMonth(year, month);

  useScrollRestore('photo', isLoading);

  const eventClusters = useMemo(
    () => groupByAdaptiveClusters(data?.items ?? []),
    [data],
  );

  const heading = useMemo(() => {
    if (year === null || month === null) return 'Invalid month';
    return format(new Date(year, month - 1, 1), 'MMMM yyyy');
  }, [year, month]);

  useEffect(() => {
    if (data) setPageHeader(heading, `${data.count.toLocaleString()} photos`);
    return () => setPageHeader(null);
  }, [heading, data, setPageHeader]);

  if (year === null || month === null) {
    return <EmptyState title="Invalid month" description="Please select a valid month from Library > Months." />;
  }

  if (isLoading) return <Spinner />;

  if (!data || data.items.length === 0) {
    return <EmptyState title={heading} description="No photos found for this month." />;
  }

  return (
    <div className="space-y-6">
      <div className="space-y-8">
        {eventClusters.map((cluster) => (
          <section
            key={cluster.key}
            id={`event-${cluster.key}`}
            data-event-key={cluster.key}
            className="space-y-5"
          >
            <div className="space-y-5">
              {cluster.groups.map((group) => (
                <section key={group.key} className="space-y-2">
                  <h3 className="text-sm font-medium text-gray-700">{group.label}</h3>
                  <JustifiedPhotoGrid
                    photos={group.photos}
                    returnTo={`/library/month/${year}/${month}`}
                    navPhotoIds={data.items.map((p) => p.id)}
                  />
                </section>
              ))}
            </div>
          </section>
        ))}
      </div>

      <EventScrollScrubber
        markers={eventClusters.map((cluster, eventIndex) => ({
          key: cluster.key,
          label: cluster.marker,
          title: `Event ${eventIndex + 1} • ${cluster.title}`,
        }))}
      />
    </div>
  );
}
