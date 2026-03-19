import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInView } from 'react-intersection-observer';
import { usePhotos } from '../hooks/usePhotos';
import { groupByYearMonth, type YearGroup, type MonthGroup } from '../utils/groupByYear';
import { groupByMonth } from '../utils/groupByMonth';
import JustifiedPhotoGrid from '../components/photos/JustifiedPhotoGrid';
import { useScrollRestore } from '../hooks/useScrollRestore';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import { getThumbnailUrl } from '../api/photos';
import AuthImage from '../components/common/AuthImage';
import type { Photo } from '../types/photo';

type View = 'years' | 'months' | 'all';

function parseView(param: string | null): View {
  if (param === 'years' || param === 'months') return param;
  return 'all';
}

// ─── Year card ────────────────────────────────────────────────────────────────

function YearCard({
  yearGroup,
  hasMore,
  onClick,
}: {
  yearGroup: YearGroup;
  hasMore: boolean;
  onClick: () => void;
}) {
  const cover = yearGroup.coverPhoto;
  return (
    <button
      onClick={onClick}
      className="relative overflow-hidden rounded-2xl aspect-square group focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
    >
      {cover ? (
        <AuthImage
          src={getThumbnailUrl(cover.id, 'md')}
          alt={String(yearGroup.year)}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          loading="eager"
        />
      ) : (
        <div className="w-full h-full bg-gray-200 animate-pulse" />
      )}
      {/* Gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/15 to-transparent" />
      <div className="absolute bottom-4 left-4 text-left text-white">
        <div className="text-3xl font-bold leading-none tracking-tight">{yearGroup.year}</div>
        <div className="mt-1 text-xs font-medium opacity-75">
          {yearGroup.count.toLocaleString()}
          {hasMore ? '+' : ''} photos
        </div>
      </div>
    </button>
  );
}

// ─── Month card ───────────────────────────────────────────────────────────────

function MonthCard({
  monthGroup,
  onClick,
}: {
  monthGroup: MonthGroup;
  onClick: () => void;
}) {
  const cover = monthGroup.photos.slice(0, 4);
  const [monthLabel, yearLabel] = monthGroup.label.split(' ');

  return (
    <button
      onClick={onClick}
      className="group text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 rounded-xl"
    >
      {/* 2×2 mosaic */}
      <div className="grid grid-cols-2 gap-0.5 rounded-xl overflow-hidden aspect-square bg-gray-100">
        {[0, 1, 2, 3].map((i) => {
          const p = cover[i];
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
          {yearLabel} · {monthGroup.photos.length.toLocaleString()} photos
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

  const { data, isLoading, fetchNextPage, hasNextPage, isFetchingNextPage } = usePhotos(
    'date_taken',
    'image',
  );

  // All Photos view: lazy-load via infinite scroll sentinel
  useEffect(() => {
    if (view === 'all' && inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [view, inView, hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Years / Months views: eagerly fetch all pages so cards populate
  useEffect(() => {
    if ((view === 'years' || view === 'months') && hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  // Re-run each time a new page lands so we keep chaining
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, hasNextPage, isFetchingNextPage, data?.pages.length]);

  const allPhotos: Photo[] = useMemo(
    () => data?.pages.flatMap((page) => page.items) ?? [],
    [data],
  );

  const years = useMemo(() => groupByYearMonth(allPhotos), [allPhotos]);
  const monthGroups = useMemo(() => groupByMonth(allPhotos), [allPhotos]);

  // Restore scroll position when returning from PhotoDetailPage
  useScrollRestore('photo', view !== 'all' || isLoading);

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
      // Poll briefly to wait for the section to be rendered
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

  if (isLoading) return <Spinner />;
  if (allPhotos.length === 0)
    return (
      <EmptyState title="No photos yet" description="Add photos to your library to get started" />
    );

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

        {/* Right: loading progress for year/month views */}
        <div className="flex justify-end">
          {(view === 'years' || view === 'months') && hasNextPage && (
            <span className="text-xs text-gray-400 flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 border-2 border-gray-300 border-t-primary-500 rounded-full animate-spin" />
              {allPhotos.length.toLocaleString()} loaded…
            </span>
          )}
        </div>
      </div>

      {/* ── Years view ── */}
      {view === 'years' && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {years.map((yg) => (
            <YearCard
              key={yg.year}
              yearGroup={yg}
              hasMore={hasNextPage ?? false}
              onClick={() => goToYear(yg.year)}
            />
          ))}
        </div>
      )}

      {/* ── Months view ── */}
      {view === 'months' && (
        <div className="space-y-10">
          {years.map((yg) => (
            <section key={yg.year} id={`year-section-${yg.year}`}>
              <div className="flex items-baseline gap-3 mb-5">
                <h2 className="text-4xl font-bold text-gray-900">{yg.year}</h2>
                <span className="text-sm text-gray-400">
                  {yg.count.toLocaleString()}
                  {hasNextPage ? '+' : ''} photos
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-5">
                {yg.months.map((mg) => (
                  <MonthCard key={mg.key} monthGroup={mg} onClick={() => goToMonth(mg.key)} />
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
