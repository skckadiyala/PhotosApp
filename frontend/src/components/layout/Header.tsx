import { useState } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';

type LibraryView = 'years' | 'months' | 'all';

function parseView(p: string | null): LibraryView {
  if (p === 'years' || p === 'months') return p;
  return 'all';
}

const LIBRARY_VIEWS = [
  { value: 'years' as LibraryView, label: 'Years' },
  { value: 'months' as LibraryView, label: 'Months' },
  { value: 'all' as LibraryView, label: 'All Photos' },
];

const VIDEO_VIEWS = [
  { value: 'years' as LibraryView, label: 'Years' },
  { value: 'months' as LibraryView, label: 'Months' },
  { value: 'all' as LibraryView, label: 'All Videos' },
];

const STATIC_TITLES: Record<string, string> = {
  '/people': 'People',
  '/favorites': 'Favorites',
  '/albums': 'Albums',
  '/map': 'Map',
  '/search': 'Search',
};

function ChevronLeft() {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  );
}

export default function Header() {
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const pageTitle = useUIStore((s) => s.pageTitle);
  const pageSubtitle = useUIStore((s) => s.pageSubtitle);
  const selectionMode = useUIStore((s) => s.selectionMode);
  const enterSelectionMode = useUIStore((s) => s.enterSelectionMode);
  const clearSelection = useUIStore((s) => s.clearSelection);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');

  const { pathname } = location;

  // Route classification
  const isLibraryArea  = pathname.startsWith('/library');
  const isVideosArea   = pathname.startsWith('/videos');
  const isLibraryMonth = pathname.startsWith('/library/month/');
  const isLibraryEvent = pathname.startsWith('/library/event/');
  const isVideosMonth  = pathname.startsWith('/videos/month/');
  const isVideosEvent  = pathname.startsWith('/videos/event/');
  const isLibrarySubPage = isLibraryMonth || isLibraryEvent;
  const isVideosSubPage  = isVideosMonth  || isVideosEvent;

  // Active tab per area
  const libraryView: LibraryView = isLibraryMonth ? 'months' : isLibraryEvent ? 'all' : parseView(searchParams.get('view'));
  const videosView:  LibraryView = isVideosMonth  ? 'months' : isVideosEvent  ? 'all' : parseView(searchParams.get('view'));

  // Back-link config for sub-pages
  const libraryBack = isLibraryMonth ? { to: '/library?view=months', label: 'Months' }
                    : isLibraryEvent ? { to: '/library?view=all',    label: 'All Photos' }
                    : null;
  const videosBack  = isVideosMonth  ? { to: '/videos?view=months',  label: 'Months' }
                    : isVideosEvent  ? { to: '/videos?view=all',      label: 'All Videos' }
                    : null;

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/search');
    if (pathname === '/search') setSearchQuery('');
  };

  // ── Shared atoms ──────────────────────────────────────────────────────────
  const hamburger = (
    <button
      onClick={toggleSidebar}
      className="flex-shrink-0 rounded-lg p-2 text-gray-500 hover:bg-gray-100"
      aria-label="Toggle sidebar"
    >
      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
      </svg>
    </button>
  );

  const searchForm = (
    <form onSubmit={handleSearchSubmit} className="w-40 sm:w-56">
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search…"
          className="w-full rounded-lg border border-gray-200 bg-gray-50 pl-9 pr-3 py-1.5 text-sm placeholder-gray-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
        />
      </div>
    </form>
  );

  const logoutBtn = (
    <button onClick={logout} className="rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 hidden sm:block">
      Logout
    </button>
  );

  const selectBtn = (
    <button
      onClick={() => selectionMode ? clearSelection() : enterSelectionMode()}
      className={`text-sm font-medium transition-colors ${selectionMode ? 'text-primary-600 hover:text-primary-700' : 'text-gray-600 hover:text-gray-800'}`}
    >
      {selectionMode ? 'Done' : 'Select'}
    </button>
  );

  const rightSlot = (
    <div className="flex items-center justify-end gap-2 sm:gap-3">
      {searchForm}
      {logoutBtn}
    </div>
  );

  const rightSlotWithSelect = (
    <div className="flex items-center justify-end gap-3 sm:gap-4">
      {selectBtn}
      {searchForm}
      {logoutBtn}
    </div>
  );

  const subPageRightSlot = (
    <div className="flex items-center justify-end gap-3 sm:gap-4">
      {selectBtn}
      {logoutBtn}
    </div>
  );

  // ── Sub-page left section (shared shape for library & videos) ─────────────
  function SubPageLeft({ back }: { back: { to: string; label: string } }) {
    return (
      <div className="flex items-center gap-2 min-w-0">
        {hamburger}
        <button
          onClick={() => navigate(back.to)}
          className="flex items-center gap-0.5 text-sm font-medium text-blue-600 hover:text-blue-700 flex-shrink-0"
        >
          <ChevronLeft />
          <span className="hidden sm:inline">{back.label}</span>
        </button>
        {pageTitle && (
          <>
            <span className="text-gray-300 flex-shrink-0 hidden sm:inline">/</span>
            <div className="min-w-0 hidden sm:block">
              <p className="text-[14px] font-semibold text-gray-900 truncate leading-tight">{pageTitle}</p>
              {pageSubtitle && <p className="text-[11px] text-gray-400 leading-tight">{pageSubtitle}</p>}
            </div>
          </>
        )}
      </div>
    );
  }

  // ── Segmented control ─────────────────────────────────────────────────────
  function SegControl({ views, active, onSelect }: { views: typeof LIBRARY_VIEWS; active: LibraryView; onSelect: (v: LibraryView) => void }) {
    return (
      <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
        {views.map(({ value: v, label }) => (
          <button
            key={v}
            onClick={() => onSelect(v)}
            className={`px-2.5 sm:px-4 py-1.5 text-xs sm:text-sm font-medium rounded-md transition-all ${
              active === v ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    );
  }

  const headerClass = 'grid h-14 items-center border-b border-gray-200 bg-white px-3 sm:px-4';
  const cols = { style: { gridTemplateColumns: '1fr auto 1fr' } };

  // ── Library area ──────────────────────────────────────────────────────────
  if (isLibraryArea) {
    if (isLibrarySubPage && libraryBack) {
      return (
        <header className={headerClass} {...cols}>
          <SubPageLeft back={libraryBack} />
          <div />
          {subPageRightSlot}
        </header>
      );
    }
    return (
      <header className={headerClass} {...cols}>
        <div className="flex items-center gap-2 min-w-0">
          {hamburger}
          <span className="text-[15px] font-semibold text-gray-900">Library</span>
        </div>
        <SegControl
          views={LIBRARY_VIEWS}
          active={libraryView}
          onSelect={(v) => navigate(v === 'all' ? '/library?view=all' : `/library?view=${v}`)}
        />
        {rightSlotWithSelect}
      </header>
    );
  }

  // ── Videos area ───────────────────────────────────────────────────────────
  if (isVideosArea) {
    if (isVideosSubPage && videosBack) {
      return (
        <header className={headerClass} {...cols}>
          <SubPageLeft back={videosBack} />
          <div />
          {subPageRightSlot}
        </header>
      );
    }
    return (
      <header className={headerClass} {...cols}>
        <div className="flex items-center gap-2 min-w-0">
          {hamburger}
          <span className="text-[15px] font-semibold text-gray-900">Videos</span>
        </div>
        <SegControl
          views={VIDEO_VIEWS}
          active={videosView}
          onSelect={(v) => navigate(v === 'all' ? '/videos?view=all' : `/videos?view=${v}`)}
        />
        {rightSlotWithSelect}
      </header>
    );
  }

  // ── All other pages ───────────────────────────────────────────────────────
  const title = STATIC_TITLES[pathname] ?? pageTitle ?? '';
  return (
    <header className={headerClass} {...cols}>
      <div className="flex items-center gap-3">
        {hamburger}
        {title && <span className="text-[15px] font-semibold text-gray-900">{title}</span>}
      </div>
      <div />
      {rightSlot}
    </header>
  );
}
