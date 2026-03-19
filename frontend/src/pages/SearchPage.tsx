import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInView } from 'react-intersection-observer';
import { useSearch } from '../hooks/useSearch';
import { usePeople } from '../hooks/useFaces';
import JustifiedPhotoGrid from '../components/photos/JustifiedPhotoGrid';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import type { Photo } from '../types/photo';

export default function SearchPage() {
  const [urlParams] = useSearchParams();
  const [query, setQuery] = useState(() => urlParams.get('q') ?? '');

  // Sync query when the URL ?q= param changes (e.g. navigated from header search)
  useEffect(() => {
    const q = urlParams.get('q') ?? '';
    setQuery(q);
  }, [urlParams]);
  const [personId, setPersonId] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [year, setYear] = useState('');
  const [location, setLocation] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const { data: people } = usePeople();

  const searchParams = useMemo(() => {
    // If year field is a valid 4-digit year, use it to compute a date range
    const parsedYear = /^(19|20)\d{2}$/.test(year.trim()) ? year.trim() : '';
    return {
      q: query || undefined,
      person_id: personId || undefined,
      from_date: parsedYear ? `${parsedYear}-01-01` : (fromDate || undefined),
      to_date: parsedYear ? `${parsedYear}-12-31` : (toDate || undefined),
      location: location || undefined,
    };
  }, [query, personId, fromDate, toDate, location, year]);

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = useSearch(searchParams);
  const { ref, inView } = useInView();

  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const allPhotos: Photo[] = useMemo(
    () => data?.pages.flatMap((page) => page.items) ?? [],
    [data],
  );

  const hasActiveSearch = Boolean(query || personId || fromDate || toDate || location || year);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-gray-900">
          {query ? `Results for "${query}"` : 'Search'}
        </h1>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`flex-shrink-0 rounded-lg border px-4 py-2 text-sm ${
            showFilters || personId || fromDate || toDate || location || year
              ? 'border-primary-500 bg-primary-50 text-primary-700'
              : 'border-gray-300 text-gray-600 hover:bg-gray-50'
          }`}
        >
          Filters{(personId || fromDate || toDate || location || year) ? ' •' : ''}
        </button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="mb-6 grid grid-cols-1 gap-4 rounded-lg border border-gray-200 bg-white p-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Person filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Person</label>
            <select
              value={personId}
              onChange={(e) => setPersonId(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            >
              <option value="">All people</option>
              {people?.map((p) => (
                <option key={p.id} value={p.id}>{p.name || `Unknown (${p.face_count})`}</option>
              ))}
            </select>
          </div>

          {/* Location filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Location</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Alaska, Paris…"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400"
            />
          </div>

          {/* Year filter */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Year</label>
            <input
              type="text"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              placeholder="e.g. 2024"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-400"
            />
          </div>

          {/* Date range (for exact range; overridden when Year is set) */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              From date{year ? ' (overridden by Year)' : ''}
            </label>
            <input
              type="date"
              value={fromDate}
              disabled={Boolean(year)}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:opacity-40"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              To date{year ? ' (overridden by Year)' : ''}
            </label>
            <input
              type="date"
              value={toDate}
              disabled={Boolean(year)}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm disabled:opacity-40"
            />
          </div>

          {hasActiveSearch && (
            <div className="sm:col-span-2 lg:col-span-3">
              <button
                onClick={() => { setQuery(''); setPersonId(''); setFromDate(''); setToDate(''); setLocation(''); setYear(''); }}
                className="text-sm text-primary-600 hover:text-primary-800"
              >
                Clear all filters
              </button>
            </div>
          )}
        </div>
      )}

      {/* Results */}
      {isLoading && <Spinner />}

      {!isLoading && hasActiveSearch && allPhotos.length === 0 && (
        <EmptyState title="No results" description="Try different search terms or filters" icon="🔍" />
      )}

      {!hasActiveSearch && (
        <EmptyState title="Search your photos" description="Enter a search term, a location (e.g. Alaska) or use filters to find photos" icon="🔍" />
      )}

      {allPhotos.length > 0 && (
        <>
          <p className="mb-3 text-sm text-gray-500">{allPhotos.length} results</p>
          <JustifiedPhotoGrid photos={allPhotos} returnTo="/search" />
        </>
      )}

      <div ref={ref} className="h-10" />
      {isFetchingNextPage && <Spinner />}
    </div>
  );
}
