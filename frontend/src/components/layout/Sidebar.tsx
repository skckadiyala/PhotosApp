import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useUIStore } from '../../stores/uiStore';
import { triggerScan, rescanFaces } from '../../api/photos';
import { clsx } from 'clsx';

const navItems = [
  { to: '/library', label: 'Library', icon: '📷' },
  { to: '/videos', label: 'Videos', icon: '🎬' },
  { to: '/albums', label: 'Albums', icon: '📁' },
  { to: '/people', label: 'People', icon: '👤' },
  { to: '/map', label: 'Map', icon: '🗺️' },
  { to: '/favorites', label: 'Favorites', icon: '❤️' },
];

export default function Sidebar() {
  const sidebarOpen = useUIStore((s) => s.sidebarOpen);
  const queryClient = useQueryClient();
  const [scanning, setScanning] = useState(false);
  const [rescanning, setRescanning] = useState(false);

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['photos'] });
    queryClient.invalidateQueries({ queryKey: ['people'] });
    queryClient.invalidateQueries({ queryKey: ['faces'] });
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerScan();
      toast.success('Scanning library & detecting faces — this may take a minute');
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ['photos'] }), 3000);
      setTimeout(() => { invalidateAll(); setScanning(false); }, 15000);
    } catch {
      toast.error('Failed to start scan');
      setScanning(false);
    }
  };

  const handleRescanFaces = async () => {
    setRescanning(true);
    try {
      await rescanFaces();
      toast.success('Re-scanning all faces — this may take a few minutes');
      setTimeout(() => { invalidateAll(); setRescanning(false); }, 30000);
    } catch {
      toast.error('Failed to start face rescan');
      setRescanning(false);
    }
  };

  return (
    <aside
      className={clsx(
        'fixed left-0 top-0 z-30 hidden md:flex flex-col h-full bg-white border-r border-gray-200 transition-all duration-200',
        sidebarOpen ? 'w-64' : 'w-16',
      )}
    >
      <div className="flex h-14 items-center gap-3 border-b border-gray-200 px-4">
        <span className="text-xl">📸</span>
        {sidebarOpen && (
          <span className="text-lg font-semibold text-gray-800">PhotosApp</span>
        )}
      </div>

      <nav className="flex-1 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-50 text-primary-700 border-r-2 border-primary-600'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
              )
            }
          >
            <span className="text-lg">{item.icon}</span>
            {sidebarOpen && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* ── Bottom actions ── */}
      <div className="border-t border-gray-100 py-3">
        <button
          onClick={handleScan}
          disabled={scanning || rescanning}
          title="Scan library for new photos and detect faces"
          className={clsx(
            'flex w-full items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors',
            'text-gray-600 hover:bg-gray-50 hover:text-gray-900 disabled:opacity-50',
          )}
        >
          <span className="text-lg flex-shrink-0">
            {scanning ? (
              <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            ) : '🔍'}
          </span>
          {sidebarOpen && <span>{scanning ? 'Scanning…' : 'Scan Library'}</span>}
        </button>

        <button
          onClick={handleRescanFaces}
          disabled={rescanning || scanning}
          title="Re-detect all faces with improved accuracy"
          className={clsx(
            'flex w-full items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors',
            'text-gray-600 hover:bg-gray-50 hover:text-gray-900 disabled:opacity-50',
          )}
        >
          <span className="text-lg flex-shrink-0">
            {rescanning ? (
              <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            ) : '🧑‍🤝‍🧑'}
          </span>
          {sidebarOpen && <span>{rescanning ? 'Rescanning…' : 'Rescan Faces'}</span>}
        </button>
      </div>
    </aside>
  );
}
