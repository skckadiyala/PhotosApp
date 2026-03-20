import { useEffect, useMemo, useState } from 'react';

interface Marker {
  key: string;
  label: string;
  title: string;
}

interface EventScrollScrubberProps {
  markers: Marker[];
}

export default function EventScrollScrubber({ markers }: EventScrollScrubberProps) {
  const [activeKey, setActiveKey] = useState<string | null>(markers[0]?.key ?? null);

  const validMarkers = useMemo(() => markers.filter((m) => !!m.key), [markers]);

  useEffect(() => {
    if (validMarkers.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (visible.length === 0) return;
        const key = visible[0].target.getAttribute('data-event-key');
        if (key) setActiveKey(key);
      },
      {
        root: null,
        rootMargin: '-80px 0px -35% 0px',
        threshold: [0.1, 0.3, 0.5, 0.8],
      },
    );

    validMarkers.forEach((marker) => {
      const section = document.querySelector(`[data-event-key="${marker.key}"]`);
      if (section) observer.observe(section);
    });

    return () => observer.disconnect();
  }, [validMarkers]);

  if (validMarkers.length === 0) return null;

  const scrollToEvent = (key: string) => {
    const section = document.querySelector(`[data-event-key="${key}"]`);
    if (section) {
      (section as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="pointer-events-none fixed right-2 top-20 z-30 select-none">
      <div className="pointer-events-auto flex max-h-[70vh] flex-col items-end gap-1 overflow-y-auto rounded-lg bg-white/70 px-1 py-1 backdrop-blur-sm">
        {validMarkers.map((marker) => (
          <button
            key={marker.key}
            onClick={() => scrollToEvent(marker.key)}
            title={marker.title}
            className={`rounded px-1.5 py-0.5 text-[11px] font-medium transition-all ${
              activeKey === marker.key
                ? 'bg-blue-50 text-blue-600'
                : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'
            }`}
          >
            {marker.label}
          </button>
        ))}
      </div>
    </div>
  );
}
