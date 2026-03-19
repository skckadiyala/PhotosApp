import { useState, useEffect, forwardRef } from 'react';
import type { CSSProperties } from 'react';
import { useAuthStore } from '../../stores/authStore';

interface Props {
  src: string;
  alt: string;
  className?: string;
  style?: CSSProperties;
  loading?: 'lazy' | 'eager';
  onLoad?: () => void;
  onError?: () => void;
}

// ── Module-level blob URL cache (max 60 entries, FIFO eviction) ──────────────
const MAX_CACHE = 60;
const blobUrlCache = new Map<string, string>();

function cacheSet(key: string, value: string) {
  if (blobUrlCache.size >= MAX_CACHE) {
    // Just drop the map entry — do NOT revoke the URL.
    // Revoking while an <img> still holds a reference causes ERR_FILE_NOT_FOUND.
    // The browser frees the underlying blob data once all <img> references are gone.
    const firstKey = blobUrlCache.keys().next().value!;
    blobUrlCache.delete(firstKey);
  }
  blobUrlCache.set(key, value);
}

/** Returns true if the image src is already in the blob cache (renders instantly). */
export function isImageCached(src: string): boolean {
  return blobUrlCache.has(src);
}

/** Prefetch an auth-protected image into the blob cache without rendering it. */
export async function prefetchAuthImage(src: string, token: string): Promise<void> {
  if (!src || !token || blobUrlCache.has(src)) return;
  try {
    const res = await fetch(src, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) return;
    const blob = await res.blob();
    cacheSet(src, URL.createObjectURL(blob));
  } catch {
    // Prefetch errors are silent
  }
}

/**
 * Image component that fetches auth-protected image endpoints via Bearer token.
 *
 * - Reads from the blob cache SYNCHRONOUSLY during render: cached images
 *   appear on the very first frame with zero async gap.
 * - asyncState is keyed by src to prevent stale images when src changes.
 * - No fetchingSrc guard: works correctly under React StrictMode.
 */
const AuthImage = forwardRef<HTMLImageElement, Props>(
  ({ src, alt, className, style, loading = 'lazy', onLoad, onError }, ref) => {
  const token = useAuthStore((s) => s.accessToken);

  // Tracks async-loaded blob URLs; keyed by src to prevent stale display
  const [asyncState, setAsyncState] = useState<{ src: string; url: string } | null>(null);

  // Synchronous cache read — cached images appear with zero delay
  const blobUrl = blobUrlCache.get(src) ?? (asyncState?.src === src ? asyncState.url : null);

  useEffect(() => {
    if (!src || !token) return;
    if (blobUrlCache.has(src)) return; // already cached, derived synchronously above

    let cancelled = false;
    const controller = new AbortController();

    fetch(src, {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        if (!cancelled) {
          const url = URL.createObjectURL(blob);
          cacheSet(src, url);
          setAsyncState({ src, url });
        }
      })
      .catch(() => {
        if (!cancelled) onError?.();
      });

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [src, token, onError]);

  if (!blobUrl) return null;

  return (
    <img
      ref={ref}
      src={blobUrl}
      alt={alt}
      className={className}
      style={style}
      loading={loading}
      onLoad={onLoad}
    />
  );
});

AuthImage.displayName = 'AuthImage';
export default AuthImage;
