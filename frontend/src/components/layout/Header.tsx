import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useAuthStore } from '../../stores/authStore';
import { useUIStore } from '../../stores/uiStore';
import { triggerScan, rescanFaces } from '../../api/photos';

export default function Header() {
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const logout = useAuthStore((s) => s.logout);
  const queryClient = useQueryClient();
  const [scanning, setScanning] = useState(false);
  const [rescanning, setRescanning] = useState(false);

  const invalidatePeopleQueries = () => {
    queryClient.invalidateQueries({ queryKey: ['photos'] });
    queryClient.invalidateQueries({ queryKey: ['people'] });
    queryClient.invalidateQueries({ queryKey: ['faces'] });
  };

  const handleScan = async () => {
    setScanning(true);
    try {
      await triggerScan();
      toast.success('Scanning library & detecting faces — this may take a minute');
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: ['photos'] });
      }, 3000);
      setTimeout(() => {
        invalidatePeopleQueries();
        setScanning(false);
      }, 15000);
    } catch {
      toast.error('Failed to start scan');
      setScanning(false);
    }
  };

  const handleRescanFaces = async () => {
    setRescanning(true);
    try {
      await rescanFaces();
      toast.success('Re-scanning all faces with improved detection — this may take a few minutes');
      setTimeout(() => {
        invalidatePeopleQueries();
        setRescanning(false);
      }, 30000);
    } catch {
      toast.error('Failed to start face rescan');
      setRescanning(false);
    }
  };

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4">
      <button
        onClick={toggleSidebar}
        className="rounded-lg p-2 text-gray-500 hover:bg-gray-100"
        aria-label="Toggle sidebar"
      >
        <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>

      <div className="flex items-center gap-3">
        <button
          onClick={handleScan}
          disabled={scanning}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-50"
          title="Scan library for new photos"
        >
          <svg className={`h-4 w-4 ${scanning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          {scanning ? 'Scanning...' : 'Scan'}
        </button>
        <button
          onClick={handleRescanFaces}
          disabled={rescanning || scanning}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 disabled:opacity-50"
          title="Re-detect all faces with improved accuracy and re-cluster"
        >
          <svg className={`h-4 w-4 ${rescanning ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {rescanning ? 'Rescanning...' : 'Rescan Faces'}
        </button>
        <button
          onClick={logout}
          className="rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
