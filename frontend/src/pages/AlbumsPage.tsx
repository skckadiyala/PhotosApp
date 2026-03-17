import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAlbums } from '../hooks/useAlbums';
import { createAlbum } from '../api/albums';
import { getThumbnailUrl } from '../api/photos';
import AuthImage from '../components/common/AuthImage';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import toast from 'react-hot-toast';
import type { Album } from '../types/album';

export default function AlbumsPage() {
  const { data, isLoading } = useAlbums();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');

  const createMutation = useMutation({
    mutationFn: () => createAlbum(newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['albums'] });
      setShowCreate(false);
      setNewName('');
      toast.success('Album created');
    },
    onError: () => toast.error('Failed to create album'),
  });

  if (isLoading) return <Spinner />;

  const albums: Album[] = data?.items ?? [];

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">Albums</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          + New Album
        </button>
      </div>

      {/* Create album modal */}
      {showCreate && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="mb-2 text-sm font-medium">Create Album</h3>
          <div className="flex gap-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && newName.trim() && createMutation.mutate()}
              placeholder="Album name"
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              autoFocus
            />
            <button
              onClick={() => createMutation.mutate()}
              disabled={!newName.trim() || createMutation.isPending}
              className="rounded-lg bg-primary-600 px-4 py-2 text-sm text-white hover:bg-primary-700 disabled:opacity-50"
            >
              Create
            </button>
            <button
              onClick={() => { setShowCreate(false); setNewName(''); }}
              className="rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {albums.length === 0 ? (
        <EmptyState title="No albums" description="Create an album to organize your photos" icon="📁" />
      ) : (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
          {albums.map((album) => (
            <button
              key={album.id}
              onClick={() => navigate(`/albums/${album.id}`)}
              className="group overflow-hidden rounded-xl bg-white shadow-sm hover:shadow-md transition-shadow text-left"
            >
              <div className="aspect-square bg-gray-100 overflow-hidden">
                {album.cover_photo_id ? (
                  <AuthImage
                    src={getThumbnailUrl(album.cover_photo_id, 'md')}
                    alt={album.name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-4xl">📁</div>
                )}
              </div>
              <div className="p-3">
                <h3 className="text-sm font-medium text-gray-900 group-hover:text-primary-600 truncate">
                  {album.name}
                </h3>
                <p className="text-xs text-gray-500">{album.photo_count} photos</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
