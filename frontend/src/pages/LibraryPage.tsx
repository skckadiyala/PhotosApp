import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInView } from 'react-intersection-observer';
import { usePhotos, useLibrarySummary } from '../hooks/usePhotos';
import { groupByMonth } from '../utils/groupByMonth';
import JustifiedPhotoGrid from '../components/photos/JustifiedPhotoGrid';
import { useScrollRestore } from '../hooks/useScrollRestore';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import { getThumbnailUrl } from '../api/photos';
import AuthImage from '../components/common/AuthImage';
import type { Photo, YearSummary, MonthSummary } from '../types/photo';

type View = 'years' | 'months' | 'all';

function parseView(param: string | null): View {
  if (param === 'years' || param === 'months') return param;
  return 'all';
}

// ─── Year card (uses summary data — no full photo fetch required) ─────────────

function YearCard({
  year,
  onClick,
}: {
  year: YearSummary;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="relative overflow-hidden rounded-2xl aspect-square group focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
    >
      {year.cover_photo ? (
        <AuthImage
          src={getThumbnailUrl(year.cover_photo.id, 'md')}
          alt={String(year.year)}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          loading="eager"
        />
      ) : (
        <div className="w-full h-full bg-gray-200 animate-pulse" />
      )}
      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/15 to-transparent" />
      <div className="absolute bottom-4 left-4 text-left text-white">
        <div className="text-3xl font-bold leading-none tracking-tight">{year.year}</div>
        <div className="mt-1 text-xs font-medium opacity-75">
          {year.count.toLocaleString()} photos
        </div>
      </div>
    </button>
  );
}

// ─── Month card (uses summary data — no full photo fetch required) ────────────

function MonthCard({
  month,
  onClick,
}: {
  month: MonthSummary;
  onClick: () => void;
}) {
  const [monthLabel, yearLabel] = month.label.split(' ');

  return (
    <button
      onClick={onClick}
      className="group text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 rounded-xl"
    >
      {/* 2×2 mosaic */}
      <div className="grid grid-cols-2 gap-0.5 rounded-xl overflow-hidden aspect-square bg-gray-100">
        {[0, 1, 2, 3].map((i) => {
          const p = month.cover_photos[i];
          return (
            <div key={i} className="overflow-hidden bg-gray-100">
              {p ? (
                <AuthImage
                  src={getThumbnailUrl(p.id, 'sm')}
                  alt=""
                  className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                  loading="lazy"
                />
              ) : (
                <div className="w-full h-full bg-gray-100" />
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-2 px-0.5">
        <div className="text-sm font-semibold text-gray-900">{monthLabel}</div>
        <div className="text-xs text-gray-400">
          {yearLabel} · {month.count.toLocaleString()} photos
        </div>
      </div>
    </button>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function LibraryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const view = parseView(searchParams.get('view'));
  const highlightYear = searchParams.get('year') ? Number(searchParams.get('year')) : null;

  // Ref used to pass a month scroll target across the view-switch render cycle
  const scrollTargetMonthRef = useRef<string | null>(null);

  const { ref: sentinelRef, inView } = useInView();

  // Years/Months views: single API call returns pre-aggregated groupings
  const { data: summary, isLoading: summaryLoading } = useLibrarySummary();

  // All Photos view: infinite scroll of actual photo objects
  const { data, isLoading: photosLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = usePhotos(
    'date_taken',
    'image',
  );

  // All Photos view: lazy-load via infinite scroll sentinel
  useEffect(() => {
    if (view === 'all' && inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [view, inView, hasNextPage, isFetchingNextPage, fetchNextPage]);

  const allPhotos: Photo[] = useMemo(
    () => data?.pages.flatMap((page) => page.items) ?? [],
    [data],
  );

  const monthGroups = useMemo(() => groupByMonth(allPhotos), [allPhotos]);

  // Restore scroll position when returning from PhotoDetailPage
  useScrollRestore('photo', view !== 'all' || photosLoading);

  // Scroll to highlighted year when entering Months view via Year click
  useEffect(() => {
    if (view === 'months' && highlightYear) {
      requestAnimationFrame(() => {
        document
          .getElementById(`year-section-${highlightYear}`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }, [view, highlightYear]);

  // Scroll to target month when entering All Photos view via Month click
  useEffect(() => {
    if (view === 'all' && scrollTargetMonthRef.current) {
      const target = scrollTargetMonthRef.current;
      let attempts = 0;
      const poll = () => {
        const el = document.getElementById(`section-${target}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          scrollTargetMonthRef.current = null;
        } else if (++attempts < 8) {
          setTimeout(poll, 200);
        }
      };
      requestAnimationFrame(poll);
    }
  }, [view]);

  const goToYear = useCallback(
    (year: number) => setSearchParams({ view: 'months', year: String(year) }),
    [setSearchParams],
  );

  const goToMonth = useCallback(
    (monthKey: string) => {
      scrollTargetMonthRef.current = monthKey;
      setSearchParams({ view: 'all' });
    },
    [setSearchParams],
  );

  const setView = useCallback(
    (v: View) => setSearchParams(v === 'all' ? { view: 'all' } : { view: v }),
    [setSearchParams],
  );

  // Show spinner only for the active view's data source
  const isLoading =
    (view === 'years' || view === 'months') ? summaryLoading : photosLoading;

  if (isLoading) return <Spinner />;

  if ((view === 'years' || view === 'months') && (!summary || summary.years.length === 0))
    return <EmptyState title="No photos yet" description="Add photos to your library to get started" />;

  if (view === 'all' && allPhotos.length === 0 && !photosLoading)
    return <EmptyState title="No photos yet" description="Add photos to your library to get started" />;

  return (
    <div className="flex flex-col">
      {/* ── Sticky tab bar ── */}
      <div className="sticky top-0 z-20 -mx-4 px-4 py-3 mb-6 bg-white/95 backdrop-blur-sm border-b border-gray-100 grid items-center"
        style={{ gridTemplateColumns: '1fr auto 1fr' }}
      >
        {/* Left: title */}
        <h1 className="text-lg font-semibold text-gray-900">Library</h1>

        {/* Centre: tab switcher */}
        <div className="flex items-center gap-0.5 bg-gray-100 rounded-lg p-1">
          {(['years', 'months', 'all'] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
                view === v
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {v === 'years' ? 'Years' : v === 'months' ? 'Months' : 'All Photos'}
            </button>
          ))}
        </div>

        <div className="flex justify-end" />
      </div>

      {/* ── Years view ── */}
      {view === 'years' && summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {summary.years.map((ys) => (
            <YearCard
              key={ys.year}
              year={ys}
              onClick={() => goToYear(ys.year)}
            />
          ))}
        </div>
      )}

      {/* ── Months view ── */}
      {view === 'months' && summary && (
        <div className="space-y-10">
          {summary.years.map((ys) => (
            <section key={ys.year} id={`year-section-${ys.year}`}>
              <div className="flex items-baseline gap-3 mb-5">
                <h2 className="text-4xl font-bold text-gray-900">{ys.year}</h2>
                <span className="text-sm text-gray-400">
                  {ys.count.toLocaleString()} photos
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-5">
                {ys.months.map((ms) => (
                  <MonthCard key={ms.key} month={ms} onClick={() => goToMonth(ms.key)} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* ── All Photos view ── */}
      {view === 'all' && (
        <div className="space-y-8">
          {monthGroups.map((group) => (
            <section key={group.key} id={`section-${group.key}`}>
              <h2 className="mb-3 text-lg font-medium text-gray-700 sticky top-0 bg-gray-50 py-2 z-10">
                {group.label}
              </h2>
              <JustifiedPhotoGrid
                photos={group.photos}
                returnTo="/library?view=all"
                navPhotoIds={allPhotos.map((p) => p.id)}
              />
            </section>
          ))}

          {/* Infinite scroll sentinel */}
          <div ref={sentinelRef} className="h-10" />
          {isFetchingNextPage && <Spinner />}
        </div>
      )}
    </div>
  );
}
