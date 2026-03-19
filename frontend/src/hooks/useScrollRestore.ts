import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * Restores scroll position to a previously-opened item.
 * Reads `scrollToId` from router location state and scrolls the matching
 * element into view once loading is complete.
 */
export function useScrollRestore(
  idPrefix: string,
  isLoading: boolean,
) {
  const location = useLocation();
  const scrollToId = (location.state as { scrollToId?: string } | null)?.scrollToId;

  useEffect(() => {
    if (!scrollToId || isLoading) return;
    const el = document.getElementById(`${idPrefix}-${scrollToId}`);
    if (el) el.scrollIntoView({ block: 'center', behavior: 'instant' });
  }, [scrollToId, isLoading, idPrefix]);
}
