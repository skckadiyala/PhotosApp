import { useParams, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { fetchAlbum, addPhotosToAlbum, updateAlbum } from '../api/albums';
import { fetchPhotos, getThumbnailUrl } from '../api/photos';
import { useScrollRestore } from '../hooks/useScrollRestore';
import PhotoCard from '../components/photos/PhotoCard';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import type { Photo } from '../types/photo';

export default function AlbumDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showPicker, setShowPicker] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isEditingName, setIsEditingName] = useState(false);
  const [editName, setEditName] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['album', id],
    queryFn: () => fetchAlbum(id!),
    enabled: !!id,
  });

  const { data: allPhotosData } = useQuery({
    queryKey: ['photos', 'all-for-picker'],
    queryFn: () => fetchPhotos({ page: 1, limit: 200, sort: 'date_taken' }),
    enabled: showPicker,
  });

  const renameMutation = useMutation({
    mutationFn: (name: string) => updateAlbum(id!, { name }),
    onSuccess: () => {
      toast.success('Album renamed');
      queryClient.invalidateQueries({ queryKey: ['album', id] });
      queryClient.invalidateQueries({ queryKey: ['albums'] });
      setIsEditingName(false);
    },
    onError: () => toast.error('Failed to rename album'),
  });

  const addMutation = useMutation({
    mutationFn: () => addPhotosToAlbum(id!, Array.from(selectedIds)),
    onSuccess: (result) => {
      toast.success(`Added ${result.added} photo(s) to album`);
      queryClient.invalidateQueries({ queryKey: ['album', id] });
      queryClient.invalidateQueries({ queryKey: ['albums'] });
      setShowPicker(false);
      setSelectedIds(new Set());
    },
    onError: () => toast.error('Failed to add photos'),
  });

  const togglePhoto = (photoId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(photoId)) next.delete(photoId);
      else next.add(photoId);
      return next;
    });
  };

  useScrollRestore('photo', isLoading);

  if (isLoading) return <Spinner />;
  if (!data) return <EmptyState title="Album not found" icon="📁" />;

  const photos: Photo[] = data.items ?? [];
  const existingIds = new Set(photos.map((p) => p.id));
  const pickablePhotos: Photo[] = (allPhotosData?.items ?? []).filter(
    (p: Photo) => !existingIds.has(p.id),
  );

  return (
    <div>
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate('/albums')}
          className="rounded-lg p-2 text-gray-500 hover:bg-gray-100"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        <div className="flex-1">
          {isEditingName ? (
            <form
              onSubmit={(e) => { e.preventDefault(); editName.trim() && renameMutation.mutate(editName.trim()); }}
              className="flex items-center gap-2"
            >
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="rounded-lg border border-gray-300 px-3 py-1 text-lg font-semibold focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                autoFocus
                onKeyDown={(e) => e.key === 'Escape' && setIsEditingName(false)}
              />
              <button
                type="submit"
                disabled={!editName.trim() || renameMutation.isPending}
                className="rounded-lg bg-primary-600 px-3 py-1 text-sm text-white hover:bg-primary-700 disabled:opacity-50"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => setIsEditingName(false)}
                className="rounded-lg px-3 py-1 text-sm text-gray-600 hover:bg-gray-100"
              >
                Cancel
              </button>
            </form>
          ) : (
            <button
              onClick={() => { setEditName(data.album?.name || ''); setIsEditingName(true); }}
              className="group flex items-center gap-2 text-left"
              title="Click to rename"
            >
              <h1 className="text-xl font-semibold text-gray-900">{data.album?.name || 'Album'}</h1>
              <svg className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
            </button>
          )}
          {!isEditingName && data.album?.description && (
            <p className="text-sm text-gray-500">{data.album.description}</p>
          )}
        </div>
        <button
          onClick={() => { setShowPicker(true); setSelectedIds(new Set()); }}
          className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          + Add Photos
        </button>
      </div>

      {/* Photo picker modal */}
      {showPicker && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 flex max-h-[80vh] w-full max-w-4xl flex-col rounded-xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <h2 className="text-lg font-semibold">
                Select Photos {selectedIds.size > 0 && `(${selectedIds.size} selected)`}
              </h2>
              <div className="flex gap-2">
                <button
                  onClick={() => addMutation.mutate()}
                  disabled={selectedIds.size === 0 || addMutation.isPending}
                  className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
                >
                  {addMutation.isPending ? 'Adding...' : `Add ${selectedIds.size} Photo(s)`}
                </button>
                <button
                  onClick={() => setShowPicker(false)}
                  className="rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-100"
                >
                  Cancel
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {pickablePhotos.length === 0 ? (
                <p className="py-8 text-center text-gray-500">All photos are already in this album</p>
              ) : (
                <div className="grid grid-cols-4 gap-2 sm:grid-cols-5 md:grid-cols-6">
                  {pickablePhotos.map((photo) => (
                    <button
                      key={photo.id}
                      onClick={() => togglePhoto(photo.id)}
                      className={`relative aspect-square overflow-hidden rounded-lg border-2 transition-all ${
                        selectedIds.has(photo.id)
                          ? 'border-primary-500 ring-2 ring-primary-300'
                          : 'border-transparent hover:border-gray-300'
                      }`}
                    >
                      <img
                        src={getThumbnailUrl(photo.id, 'sm', photo.thumb_sm)}
                        alt={photo.file_name}
                        className="h-full w-full object-cover"
                        loading="lazy"
                        decoding="async"
                      />
                      {selectedIds.has(photo.id) && (
                        <div className="absolute inset-0 flex items-center justify-center bg-primary-500/30">
                          <svg className="h-8 w-8 text-white drop-shadow" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
                          </svg>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {photos.length === 0 ? (
        <EmptyState title="Album is empty" description="Click '+ Add Photos' to add photos to this album" icon="📁" />
      ) : (
        <div className="grid grid-cols-3 gap-1 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
          {photos.map((photo) => (
            <div key={photo.id} id={`photo-${photo.id}`}>
              <PhotoCard
                photo={photo}
                onClick={() => navigate(`/photo/${photo.id}`, {
                    state: { photoIds: photos.map((p) => p.id), returnTo: `/albums/${id}` },
                  })}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
