import { useEffect, useRef, useState } from 'react';
import { format, parse } from 'date-fns';
import type { PhotoGroup } from '../../utils/groupByMonth';

interface MonthScrollIndicatorProps {
  groups: PhotoGroup[];
  containerRef: React.RefObject<HTMLDivElement>;
}

export default function MonthScrollIndicator({ groups, containerRef }: MonthScrollIndicatorProps) {
  const scrollIndicatorRef = useRef<HTMLDivElement>(null);
  const [activeMonth, setActiveMonth] = useState<string | null>(null);
  const scrollableRef = useRef<HTMLElement | null>(null);

  // Extract unique years and months from groups
  const monthsList = groups.map((g) => {
    const date = parse(g.key, 'yyyy-MM', new Date());
    return {
      key: g.key,
      year: date.getFullYear(),
      month: date.getMonth() + 1,
      label: g.label,
    };
  });

  const uniqueYears = [...new Set(monthsList.map((m) => m.year))].sort((a, b) => b - a);

  // Find and cache the scrollable parent element
  useEffect(() => {
    if (!containerRef.current) return;
    
    let parent = containerRef.current.parentElement;
    while (parent) {
      const overflow = window.getComputedStyle(parent).overflowY;
      if (overflow === 'auto' || overflow === 'scroll') {
        scrollableRef.current = parent;
        return;
      }
      parent = parent.parentElement;
    }
    
    // Fallback: use window
    scrollableRef.current = null;
  }, [containerRef]);

  // Detect which month section is currently in view
  useEffect(() => {
    const scrollable = scrollableRef.current;
    if (!scrollable || !containerRef.current) return;

    const handleScroll = () => {
      const container = containerRef.current;
      if (!container) return;

      // Find which month section is most visible
      let mostVisibleMonth: string | null = null;
      let maxVisibility = 0;

      for (const group of groups) {
        const element = container.querySelector(`[data-month-key="${group.key}"]`) as HTMLElement;
        if (!element) continue;

        // Get element position relative to scrollable parent
        const rect = element.getBoundingClientRect();
        const scrollableRect = scrollable.getBoundingClientRect();

        const visibleTop = Math.max(0, rect.top - scrollableRect.top);
        const visibleBottom = Math.min(
          scrollableRect.height,
          rect.bottom - scrollableRect.top
        );
        const visibleHeight = Math.max(0, visibleBottom - visibleTop);
        const visibility = visibleHeight / (rect.height || 1);

        if (visibility > maxVisibility) {
          maxVisibility = visibility;
          mostVisibleMonth = group.key;
        }
      }

      setActiveMonth(mostVisibleMonth);
    };

    scrollable.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll(); // Call once to set initial state

    return () => scrollable.removeEventListener('scroll', handleScroll);
  }, [groups, containerRef]);

  const handleMonthClick = (key: string) => {
    const scrollable = scrollableRef.current;
    const container = containerRef.current;
    const element = container?.querySelector(`[data-month-key="${key}"]`) as HTMLElement;
    
    if (!element || !scrollable) return;

    // Calculate position relative to scrollable parent
    const elementRect = element.getBoundingClientRect();
    const scrollableRect = scrollable.getBoundingClientRect();
    const offsetTop = scrollable.scrollTop + (elementRect.top - scrollableRect.top);

    scrollable.scrollTo({
      top: offsetTop - 100, // Account for sticky header
      behavior: 'smooth',
    });
  };

  // Don't render if no groups
  if (groups.length === 0) return null;

  return (
    <div
      ref={scrollIndicatorRef}
      className="pointer-events-none fixed right-2 top-20 select-none z-30"
    >
      <div className="pointer-events-auto flex flex-col items-end gap-0 pr-0 text-xs text-gray-500 transition-colors duration-200">
        {uniqueYears.map((year) => {
          const monthsInYear = monthsList.filter((m) => m.year === year);
          const isYearActive = monthsInYear.some((m) => m.key === activeMonth);

          return (
            <div key={year} className="flex flex-col items-end gap-0">
              {/* Year header */}
              <button
                onClick={() => handleMonthClick(monthsInYear[0].key)}
                className={`text-xs font-bold py-1 px-1.5 rounded transition-all duration-150 ${
                  isYearActive
                    ? 'text-gray-900 bg-white/80 backdrop-blur-sm shadow-sm'
                    : 'text-gray-400 hover:text-gray-600'
                }`}
                title={`Jump to ${year}`}
              >
                {year}
              </button>

              {/* Months under year */}
              <div className="flex flex-col gap-0">
                {monthsInYear.map((month) => {
                  const isActive = month.key === activeMonth;
                  const monthName = format(new Date(month.year, month.month - 1), 'MMM');

                  return (
                    <button
                      key={month.key}
                      onClick={() => handleMonthClick(month.key)}
                      className={`text-xs leading-snug py-0.5 px-1.5 rounded transition-all duration-150 text-center whitespace-nowrap ${
                        isActive
                          ? 'text-blue-600 bg-blue-50/80 backdrop-blur-sm font-semibold shadow-sm'
                          : 'text-gray-400 hover:text-gray-600 hover:bg-gray-50/50'
                      }`}
                      title={month.label}
                    >
                      {monthName}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
