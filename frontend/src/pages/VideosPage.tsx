import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useInView } from 'react-intersection-observer';
import { format } from 'date-fns';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useLibrarySummary, useEventClusters, usePhoto } from '../hooks/usePhotos';
import { useUIStore } from '../stores/uiStore';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import ConfirmDialog from '../components/common/ConfirmDialog';
import { getThumbnailUrl, getVideoStreamUrl, archivePhotos } from '../api/photos';
import type { YearSummary, MonthSummary, EventClusterSummary, Photo } from '../types/photo';

type View = 'years' | 'months' | 'all';

function parseView(param: string | null): View {
  if (param === 'years' || param === 'months') return param;
  return 'all';
}

// ─── Video card helpers ───────────────────────────────────────────────────────

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

function InfoRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-gray-400 mb-0.5">{label}</dt>
      <dd className={`text-sm text-gray-800 break-all ${mono ? 'font-mono text-xs leading-relaxed' : ''}`}>{value}</dd>
    </div>
  );
}

function VideoInfoModal({
  videoId,
  duration,
  onClose,
}: {
  videoId: string;
  duration: number | null;
  onClose: () => void;
}) {
  const { data: detail, isLoading } = usePhoto(videoId);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
          <h2 className="text-base font-semibold text-gray-900">Video Info</h2>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto px-5 py-4">
          {isLoading ? (
            <p className="py-4 text-center text-sm text-gray-400">Loading…</p>
          ) : detail ? (
            <dl className="space-y-3">
              <InfoRow label="File name" value={detail.file_name} />
              {detail.host_file_path && (
                <InfoRow label="Drive path" value={detail.host_file_path} mono />
              )}
              <InfoRow label="Container path" value={detail.file_path} mono />
              {detail.taken_at && (
                <InfoRow label="Date" value={format(new Date(detail.taken_at), 'MMMM d, yyyy · h:mm a')} />
              )}
              {detail.width != null && detail.height != null && (
                <InfoRow label="Dimensions" value={`${detail.width} × ${detail.height}`} />
              )}
              {duration !== null && (
                <InfoRow label="Duration" value={formatDuration(duration)} />
              )}
              {detail.file_size != null && (
                <InfoRow label="File size" value={formatBytes(detail.file_size)} />
              )}
              {detail.gps_latitude != null && detail.gps_longitude != null && (
                <InfoRow
                  label="GPS"
                  value={`${detail.gps_latitude.toFixed(6)}, ${detail.gps_longitude.toFixed(6)}`}
                />
              )}
              {detail.location_name && (
                <InfoRow label="Location" value={detail.location_name} />
              )}
              <InfoRow label="Type" value={detail.mime_type} />
            </dl>
          ) : (
            <p className="py-4 text-center text-sm text-gray-400">Unable to load details.</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Video card (inline player) ───────────────────────────────────────────────

export function VideoCard({ video, accessToken }: { video: Photo; accessToken: string | null }) {
  const [duration, setDuration] = useState<number | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [showArchiveConfirm, setShowArchiveConfirm] = useState(false);
  const [archiving, setArchiving] = useState(false);

  const queryClient = useQueryClient();
  const selectionMode = useUIStore((s) => s.selectionMode);
  const selectedPhotoIds = useUIStore((s) => s.selectedPhotoIds);
  const toggleSelect = useUIStore((s) => s.toggleSelect);
  const isSelected = selectedPhotoIds.has(video.id);

  const doArchive = async () => {
    setShowArchiveConfirm(false);
    setArchiving(true);
    try {
      await archivePhotos([video.id]);
      queryClient.invalidateQueries({ queryKey: ['photos'] });
      queryClient.invalidateQueries({ queryKey: ['library-summary'] });
      queryClient.invalidateQueries({ queryKey: ['event-clusters'] });
      queryClient.invalidateQueries({ queryKey: ['photos-by-month'] });
    } catch {
      toast.error('Failed to archive video');
    } finally {
      setArchiving(false);
    }
  };

  return (
    <>
      <div
        id={`video-${video.id}`}
        className={`relative flex flex-col overflow-hidden rounded-xl bg-gray-900 shadow${isSelected ? ' ring-2 ring-offset-2 ring-primary-500' : ''}`}
      >
        {/* Selection checkbox */}
        {selectionMode && (
          <button
            onClick={() => toggleSelect(video.id)}
            className={`absolute left-2 top-2 z-20 flex h-7 w-7 items-center justify-center rounded-full border-2 transition-colors ${
              isSelected
                ? 'border-primary-500 bg-primary-500'
                : 'border-white/80 bg-black/30 backdrop-blur-sm'
            }`}
            aria-label={isSelected ? 'Deselect video' : 'Select video'}
          >
            {isSelected && (
              <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            )}
          </button>
        )}

        <video
          src={accessToken ? getVideoStreamUrl(video.id, accessToken) : undefined}
          poster={video.thumb_md ? `/thumbnails/${video.thumb_md}` : undefined}
          controls
          preload="metadata"
          className="w-full aspect-video bg-black object-contain"
          onLoadedMetadata={(e) => setDuration((e.target as HTMLVideoElement).duration)}
        />

        <div className="px-3 py-2.5 space-y-1">
          <div className="flex items-start gap-2">
            <p className="min-w-0 flex-1 truncate text-sm font-medium text-gray-100" title={video.file_name}>
              {video.file_name}
            </p>
            {/* Archive button */}
            <button
              onClick={() => setShowArchiveConfirm(true)}
              disabled={archiving}
              className="shrink-0 rounded-full p-0.5 text-gray-400 transition-colors hover:text-amber-400 disabled:opacity-40"
              aria-label="Archive video"
              title="Archive video"
            >
              {archiving ? (
                <svg className="h-4 w-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              ) : (
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="21 8 21 21 3 21 3 8" />
                  <rect x="1" y="3" width="22" height="5" />
                  <line x1="10" y1="12" x2="14" y2="12" />
                </svg>
              )}
            </button>
            {/* Info button */}
            <button
              onClick={() => setShowInfo(true)}
              className="shrink-0 rounded-full p-0.5 text-gray-400 transition-colors hover:text-white"
              aria-label="Video info"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
            </button>
          </div>
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
            {video.file_size != null && <span>{formatBytes(video.file_size)}</span>}
            {video.width != null && video.height != null && <span>{video.width}×{video.height}</span>}
          </div>
        </div>

        {showInfo && (
          <VideoInfoModal videoId={video.id} duration={duration} onClose={() => setShowInfo(false)} />
        )}
      </div>

      <ConfirmDialog
        open={showArchiveConfirm}
        title="Archive video?"
        message={`"${video.file_name}" will be moved to the archive and hidden from your library.`}
        confirmLabel="Archive"
        onConfirm={doArchive}
        onCancel={() => setShowArchiveConfirm(false)}
      />
    </>
  );
}

// ─── Year card ────────────────────────────────────────────────────────────────

function YearCard({ year, onClick }: { year: YearSummary; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="relative overflow-hidden rounded-2xl aspect-square group focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
    >
      {year.cover_photo ? (
        <img
          src={getThumbnailUrl(year.cover_photo.id, 'md', year.cover_photo.thumb_md ?? year.cover_photo.thumb_sm)}
          alt={String(year.year)}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          loading="eager"
          decoding="async"
        />
      ) : (
        <div className="w-full h-full bg-gray-200 animate-pulse" />
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/15 to-transparent" />
      <div className="absolute bottom-4 left-4 text-left text-white">
        <div className="text-3xl font-bold leading-none tracking-tight">{year.year}</div>
        <div className="mt-1 text-xs font-medium opacity-75">
          {year.count.toLocaleString()} videos
        </div>
      </div>
    </button>
  );
}

// ─── Month card ───────────────────────────────────────────────────────────────

function MonthCard({ month, onClick }: { month: MonthSummary; onClick: () => void }) {
  const [monthLabel, yearLabel] = month.label.split(' ');

  return (
    <button
      onClick={onClick}
      className="group text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 rounded-xl"
    >
      <div className="grid grid-cols-2 gap-0.5 rounded-xl overflow-hidden aspect-square bg-gray-100">
        {[0, 1, 2, 3].map((i) => {
          const p = month.cover_photos[i];
          return (
            <div key={i} className="overflow-hidden bg-gray-100">
              {p ? (
                <img
                  src={getThumbnailUrl(p.id, 'sm', p.thumb_sm)}
                  alt=""
                  className="w-full h-full object-cover transition-transform duration-200 group-hover:scale-105"
                  loading="lazy"
                  decoding="async"
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
          {yearLabel} · {month.count.toLocaleString()} videos
        </div>
      </div>
    </button>
  );
}

// ─── Event folder card ────────────────────────────────────────────────────────

function EventFolderCard({ cluster, onClick }: { cluster: EventClusterSummary; onClick: () => void }) {
  const start = new Date(cluster.start_at);
  const end = new Date(cluster.end_at);
  const title = format(start, 'MMM d, yyyy • h:mm a');
  const subtitle = `${format(end, 'MMM d')} · ${cluster.count.toLocaleString()} videos`;

  return (
    <button
      id={`eventfolder-${cluster.cluster_id}`}
      onClick={onClick}
      className="group rounded-2xl border border-gray-100 bg-white p-3 text-left shadow-sm transition hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
    >
      <div className="mb-3 overflow-hidden rounded-xl bg-gray-100 aspect-[4/3]">
        {cluster.cover_photo ? (
          <img
            src={getThumbnailUrl(cluster.cover_photo.id, 'md', cluster.cover_photo.thumb_md ?? cluster.cover_photo.thumb_sm)}
            alt={title}
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <div className="h-full w-full bg-gray-200" />
        )}
      </div>
      <div className="space-y-1">
        <div className="text-sm font-semibold text-gray-900">{title}</div>
        <div className="text-xs text-gray-500">{subtitle}</div>
      </div>
    </button>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function VideosPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const view = parseView(searchParams.get('view'));
  const highlightYear = searchParams.get('year') ? Number(searchParams.get('year')) : null;
  const gapHours = 6;

  const { ref: sentinelRef, inView } = useInView();

  const { data: summary, isLoading: summaryLoading } = useLibrarySummary('video');

  const {
    data: eventPages,
    isLoading: eventsLoading,
    fetchNextPage: fetchNextEventPage,
    hasNextPage: hasNextEventPage,
    isFetchingNextPage: isFetchingNextEventPage,
  } = useEventClusters(gapHours, 'video');

  useEffect(() => {
    if (view === 'all' && inView && hasNextEventPage && !isFetchingNextEventPage) {
      fetchNextEventPage();
    }
  }, [view, inView, hasNextEventPage, isFetchingNextEventPage, fetchNextEventPage]);

  const eventFolders = useMemo(
    () => eventPages?.pages.flatMap((page) => page.items) ?? [],
    [eventPages],
  );

  useEffect(() => {
    if (view === 'months' && highlightYear) {
      requestAnimationFrame(() => {
        document
          .getElementById(`year-section-${highlightYear}`)
          ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }
  }, [view, highlightYear]);

  const goToYear = useCallback(
    (year: number) => setSearchParams({ view: 'months', year: String(year) }),
    [setSearchParams],
  );

  const goToMonth = useCallback(
    (monthKey: string) => {
      const [year, month] = monthKey.split('-');
      navigate(`/videos/month/${year}/${month}`);
    },
    [navigate],
  );

  const isLoading =
    (view === 'years' || view === 'months') ? summaryLoading : eventsLoading;

  if (isLoading) return <Spinner />;

  if ((view === 'years' || view === 'months') && (!summary || summary.years.length === 0))
    return <EmptyState title="No videos yet" description="Videos from your library will appear here" icon="🎬" />;

  if (view === 'all' && eventFolders.length === 0 && !eventsLoading)
    return <EmptyState title="No videos yet" description="Videos from your library will appear here" icon="🎬" />;

  return (
    <div className="flex flex-col">

      {/* ── Years view ── */}
      {view === 'years' && summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {summary.years.map((ys) => (
            <YearCard key={ys.year} year={ys} onClick={() => goToYear(ys.year)} />
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
                  {ys.count.toLocaleString()} videos
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

      {/* ── All Videos view ── */}
      {view === 'all' && (
        <div className="space-y-8">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-900">Event Folders</h2>
            <span className="text-xs text-gray-500">Gap rule: {gapHours} hours</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {eventFolders.map((cluster) => (
              <EventFolderCard
                key={cluster.cluster_id}
                cluster={cluster}
                onClick={() => navigate(`/videos/event/${cluster.cluster_id}?gap=${gapHours}`)}
              />
            ))}
          </div>

          <div ref={sentinelRef} className="h-10" />
          {isFetchingNextEventPage && <Spinner />}
        </div>
      )}
    </div>
  );
}
