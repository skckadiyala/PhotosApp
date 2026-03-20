import { useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { format } from 'date-fns';
import { usePhotosByMonth } from '../hooks/usePhotos';
import JustifiedPhotoGrid from '../components/photos/JustifiedPhotoGrid';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import { useScrollRestore } from '../hooks/useScrollRestore';

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

  const { data, isLoading } = usePhotosByMonth(year, month);

  useScrollRestore('photo', isLoading);

  const heading = useMemo(() => {
    if (year === null || month === null) return 'Invalid month';
    return format(new Date(year, month - 1, 1), 'MMMM yyyy');
  }, [year, month]);

  if (year === null || month === null) {
    return <EmptyState title="Invalid month" description="Please select a valid month from Library > Months." />;
  }

  if (isLoading) return <Spinner />;

  if (!data || data.items.length === 0) {
    return <EmptyState title={heading} description="No photos found for this month." />;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 border-b border-gray-100 pb-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{heading}</h1>
          <p className="text-sm text-gray-500">{data.count.toLocaleString()} photos</p>
        </div>
        <Link
          to={`/library?view=months&year=${year}`}
          className="text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          Back to Months
        </Link>
      </div>

      <JustifiedPhotoGrid
        photos={data.items}
        returnTo={`/library/month/${year}/${month}`}
        navPhotoIds={data.items.map((p) => p.id)}
      />
    </div>
  );
}
