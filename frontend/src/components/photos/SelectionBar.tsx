import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../../stores/uiStore';
import { useAuthStore } from '../../stores/authStore';
import { getThumbnailUrl, archivePhotos } from '../../api/photos';
import ConfirmDialog from '../common/ConfirmDialog';

export default function SelectionBar() {
  const selectionMode = useUIStore((s) => s.selectionMode);
  const selectedPhotoIds = useUIStore((s) => s.selectedPhotoIds);
  const clearSelection = useUIStore((s) => s.clearSelection);
  const token = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();
  const [showConfirm, setShowConfirm] = useState(false);

  const count = selectedPhotoIds.size;

  // Pre-fetch blobs as soon as photos are selected so they are ready synchronously
  // when the user taps Share (navigator.share must be called within the gesture).
  const blobCacheRef = useRef<Map<string, Blob>>(new Map());

  useEffect(() => {
    if (!selectionMode || count === 0) {
      blobCacheRef.current.clear();
      return;
    }

    const ids = Array.from(selectedPhotoIds);

    // Remove blobs for deselected photos
    for (const id of blobCacheRef.current.keys()) {
      if (!selectedPhotoIds.has(id)) blobCacheRef.current.delete(id);
    }

    // Fire-and-forget fetch for newly added photos
    ids.forEach(async (id) => {
      if (blobCacheRef.current.has(id)) return;
      try {
        const res = await fetch(getThumbnailUrl(id, 'md'), {
          headers: { Authorization: `Bearer ${token ?? ''}` },
        });
        if (res.ok) blobCacheRef.current.set(id, await res.blob());
      } catch {
        // prefetch errors are silent
      }
    });
  }, [selectionMode, selectedPhotoIds, count, token]);

  // Escape key cancels selection
  useEffect(() => {
    if (!selectionMode) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') clearSelection();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectionMode, clearSelection]);

  if (!selectionMode || count === 0) return null;

  // Synchronous handler — no awaits before navigator.share so the browser
  // keeps the user-gesture window open.
  const handleShare = () => {
    const ids = Array.from(selectedPhotoIds);
    const label = `${count} photo${count !== 1 ? 's' : ''}`;

    const files: File[] = [];
    for (const id of ids) {
      const blob = blobCacheRef.current.get(id);
      if (blob) files.push(new File([blob], `photo-${id}.jpg`, { type: 'image/jpeg' }));
    }

    const canShareFiles =
      files.length === ids.length &&
      typeof navigator.canShare === 'function' &&
      navigator.canShare({ files });

    const shareData: ShareData = canShareFiles
      ? { files, title: 'Photos', text: label }
      : { title: 'Photos', text: label };

    navigator
      .share(shareData)
      .then(() => clearSelection())
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
        // Files may be blocked — fall back to text-only share
        if (canShareFiles) {
          navigator.share({ title: 'Photos', text: label })
            .then(() => clearSelection())
            .catch(() => {});
        }
      });
  };

  const handleArchive = () => setShowConfirm(true);

  const doArchive = async () => {
    setShowConfirm(false);
    const ids = Array.from(selectedPhotoIds);
    try {
      const result = await archivePhotos(ids);
      if (result.errors.length > 0 && result.archived.length === 0) {
        alert(`Failed to archive: ${result.errors[0].error}`);
        return;
      }
      clearSelection();
      await queryClient.resetQueries({ queryKey: ['photos'] });
      await queryClient.invalidateQueries({ queryKey: ['library-summary'] });
      await queryClient.invalidateQueries({ queryKey: ['event-clusters'] });
      await queryClient.invalidateQueries({ queryKey: ['photos-by-month'] });
    } catch (err) {
      console.error('Archive failed:', err);
      alert('Failed to archive some items. Please try again.');
    }
  };

  const canShare = typeof navigator.share === 'function';

  const archiveLabel = `${count} item${count !== 1 ? 's' : ''}`;

  return (
    <>
    <ConfirmDialog
      open={showConfirm}
      title="Archive photos?"
      message={`Archive ${archiveLabel}? They will be moved to ._archive/ and hidden from your library.`}
      confirmLabel="Archive"
      destructive={false}
      onConfirm={doArchive}
      onCancel={() => setShowConfirm(false)}
    />
    <div
      className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full bg-gray-900 px-5 py-3 shadow-2xl"
      role="toolbar"
      aria-label="Selection actions"
    >
      <span className="text-sm font-semibold text-white">
        {count} {count === 1 ? 'item' : 'items'} selected
      </span>

      {canShare && (
        <>
          <div className="h-4 w-px bg-white/30" />
          <button
            onClick={handleShare}
            className="flex items-center gap-1.5 text-sm font-medium text-white transition-colors hover:text-blue-300"
            aria-label="Share selected photos"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8" />
              <polyline points="16 6 12 2 8 6" />
              <line x1="12" y1="2" x2="12" y2="15" />
            </svg>
            Share
          </button>
        </>
      )}

      <div className="h-4 w-px bg-white/30" />

      <button
        onClick={handleArchive}
        className="flex items-center gap-1.5 text-sm font-medium text-white transition-colors hover:text-amber-300"
        aria-label="Archive selected items"
      >
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="21 8 21 21 3 21 3 8" />
          <rect x="1" y="3" width="22" height="5" />
          <line x1="10" y1="12" x2="14" y2="12" />
        </svg>
        Archive
      </button>

      <div className="h-4 w-px bg-white/30" />

      <button
        onClick={clearSelection}
        className="flex items-center gap-1.5 text-sm font-medium text-white transition-colors hover:text-red-300"
        aria-label="Cancel selection"
      >
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
        Cancel
      </button>
    </div>
    </>
  );
}
