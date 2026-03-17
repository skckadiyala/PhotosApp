import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useInView } from 'react-intersection-observer';
import { useSearch } from '../hooks/useSearch';
import { usePeople } from '../hooks/useFaces';
import PhotoCard from '../components/photos/PhotoCard';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import type { Photo } from '../types/photo';

export default function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [personId, setPersonId] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const { data: people } = usePeople();

  const searchParams = useMemo(
    () => ({
      q: query || undefined,
      person_id: personId || undefined,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
    }),
    [query, personId, fromDate, toDate],
  );

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

  // Client-side filtering by file name when query is set
  const filteredPhotos = useMemo(() => {
    if (!query) return allPhotos;
    const lower = query.toLowerCase();
    return allPhotos.filter(
      (p) =>
        p.file_name.toLowerCase().includes(lower) ||
        (p.taken_at && p.taken_at.includes(query)),
    );
  }, [allPhotos, query]);

  const hasActiveSearch = Boolean(query || personId || fromDate || toDate);

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-gray-900">Search</h1>

      {/* Search bar */}
      <div className="mb-4 flex gap-2">
        <div className="relative flex-1 max-w-xl">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search photos by name, date..."
            className="w-full rounded-lg border border-gray-300 pl-10 pr-4 py-2.5 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          />
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`rounded-lg border px-4 py-2.5 text-sm ${
            showFilters ? 'border-primary-500 bg-primary-50 text-primary-700' : 'border-gray-300 text-gray-600 hover:bg-gray-50'
          }`}
        >
          Filters
        </button>
      </div>

      {/* Filter panel */}
      {showFilters && (
        <div className="mb-6 grid grid-cols-1 gap-4 rounded-lg border border-gray-200 bg-white p-4 sm:grid-cols-3">
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

          {/* Date range */}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">From date</label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">To date</label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>

          {hasActiveSearch && (
            <div className="sm:col-span-3">
              <button
                onClick={() => { setQuery(''); setPersonId(''); setFromDate(''); setToDate(''); }}
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

      {!isLoading && hasActiveSearch && filteredPhotos.length === 0 && (
        <EmptyState title="No results" description="Try different search terms or filters" icon="🔍" />
      )}

      {!hasActiveSearch && (
        <EmptyState title="Search your photos" description="Enter a search term or use filters to find photos" icon="🔍" />
      )}

      {filteredPhotos.length > 0 && (
        <>
          <p className="mb-3 text-sm text-gray-500">{filteredPhotos.length} results</p>
          <div className="grid grid-cols-3 gap-1 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
            {filteredPhotos.map((photo) => (
              <PhotoCard
                key={photo.id}
                photo={photo}
                onClick={() => navigate(`/photo/${photo.id}`)}
              />
            ))}
          </div>
        </>
      )}

      <div ref={ref} className="h-10" />
      {isFetchingNextPage && <Spinner />}
    </div>
  );
}
