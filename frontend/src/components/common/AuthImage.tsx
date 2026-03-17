import { useState, useEffect } from 'react';
import { useAuthStore } from '../../stores/authStore';

interface Props {
  src: string;
  alt: string;
  className?: string;
  loading?: 'lazy' | 'eager';
  onLoad?: () => void;
  onError?: () => void;
}

/**
 * Image component that fetches auth-protected image endpoints
 * using Bearer token, then displays via object URL.
 */
export default function AuthImage({ src, alt, className, loading = 'lazy', onLoad, onError }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const token = useAuthStore((s) => s.accessToken);

  useEffect(() => {
    if (!src || !token) return;

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
          setBlobUrl(URL.createObjectURL(blob));
        }
      })
      .catch(() => {
        if (!cancelled) onError?.();
      });

    return () => {
      cancelled = true;
      controller.abort();
      setBlobUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [src, token, onError]);

  if (!blobUrl) return null;

  return (
    <img
      src={blobUrl}
      alt={alt}
      className={className}
      loading={loading}
      onLoad={onLoad}
    />
  );
}
