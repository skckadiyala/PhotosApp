import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useCallback, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import toast from 'react-hot-toast';
import { usePhoto } from '../hooks/usePhotos';
import { useFaces, usePeople } from '../hooks/useFaces';
import { useAlbums } from '../hooks/useAlbums';
import { getOriginalUrl, getThumbnailUrl } from '../api/photos';
import { addPhotosToAlbum } from '../api/albums';
import { assignFace, getFaceThumbnailUrl } from '../api/faces';
import AuthImage from '../components/common/AuthImage';
import Spinner from '../components/common/Spinner';
import type { Face, Person } from '../types/face';
import type { Album } from '../types/album';

export default function PhotoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: photo, isLoading } = usePhoto(id);
  const { data: faces } = useFaces();
  const { data: albumsData } = useAlbums();
  const { data: peopleData } = usePeople();
  const [showInfo, setShowInfo] = useState(true);
  const [showAlbumPicker, setShowAlbumPicker] = useState(false);
  const [assigningFaceId, setAssigningFaceId] = useState<string | null>(null);
  const [newPersonName, setNewPersonName] = useState('');

  const albums: Album[] = albumsData?.items ?? [];
  const people: Person[] = peopleData ?? [];

  const addToAlbumMutation = useMutation({
    mutationFn: (albumId: string) => addPhotosToAlbum(albumId, [id!]),
    onSuccess: (_data, albumId) => {
      const album = albums.find((a) => a.id === albumId);
      toast.success(`Added to "${album?.name ?? 'album'}"`);
      queryClient.invalidateQueries({ queryKey: ['albums'] });
      queryClient.invalidateQueries({ queryKey: ['album', albumId] });
      setShowAlbumPicker(false);
    },
    onError: () => toast.error('Failed to add to album'),
  });

  const assignMutation = useMutation({
    mutationFn: (params: { faceId: string; person_id?: string; new_person_name?: string }) =>
      assignFace(params.faceId, { person_id: params.person_id, new_person_name: params.new_person_name }),
    onSuccess: (result) => {
      toast.success(result.person_name ? `Assigned to "${result.person_name}"` : 'Face assigned');
      queryClient.invalidateQueries({ queryKey: ['faces'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      setAssigningFaceId(null);
      setNewPersonName('');
    },
    onError: () => toast.error('Failed to assign face'),
  });

  const photoFaces = faces?.filter((f: Face) => f.photo_id === id) ?? [];

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') navigate(-1);
    },
    [navigate],
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (isLoading) return <Spinner />;
  if (!photo) return <div className="p-8 text-center text-gray-500">Photo not found</div>;

  return (
    <div className="fixed inset-0 z-50 flex bg-black">
      {/* Close button */}
      <button
        onClick={() => navigate(-1)}
        className="absolute left-4 top-4 z-20 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
      >
        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </button>

      {/* Info toggle */}
      <button
        onClick={() => setShowInfo(!showInfo)}
        className="absolute right-4 top-4 z-20 rounded-full bg-black/50 p-2 text-white hover:bg-black/70"
      >
        <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>

      {/* Main image area */}
      <div className="flex-1 flex items-center justify-center p-4">
        <AuthImage
          src={getOriginalUrl(photo.id)}
          alt={photo.file_name}
          className="max-h-full max-w-full object-contain"
          loading="eager"
        />
      </div>

      {/* Metadata sidebar */}
      {showInfo && (
        <aside className="w-80 flex-shrink-0 overflow-y-auto bg-gray-900 p-6 text-white">
          <h2 className="mb-4 text-lg font-semibold">{photo.file_name}</h2>

          {/* Date */}
          {photo.taken_at && (
            <InfoSection title="Date">
              <p>{format(new Date(photo.taken_at), 'EEEE, MMMM d, yyyy')}</p>
              <p className="text-sm text-gray-400">{format(new Date(photo.taken_at), 'h:mm a')}</p>
            </InfoSection>
          )}

          {/* Location */}
          {photo.gps_latitude != null && photo.gps_longitude != null && (
            <InfoSection title="Location">
              {photo.location_name && (
                <p className="text-sm font-medium text-gray-200 mb-1">{photo.location_name}</p>
              )}
              <p className="text-sm text-gray-400">
                {photo.gps_latitude.toFixed(6)}, {photo.gps_longitude.toFixed(6)}
              </p>
              <div className="mt-2 h-32 rounded-lg overflow-hidden bg-gray-800">
                <img
                  src={`https://tile.openstreetmap.org/${Math.min(15, 15)}/${lonToTile(photo.gps_longitude, 15)}/${latToTile(photo.gps_latitude, 15)}.png`}
                  alt="Map"
                  className="h-full w-full object-cover opacity-70"
                />
              </div>
            </InfoSection>
          )}

          {/* Camera */}
          {(photo.camera_make || photo.camera_model) && (
            <InfoSection title="Camera">
              <p>{[photo.camera_make, photo.camera_model].filter(Boolean).join(' ')}</p>
              {photo.lens_model && <p className="text-sm text-gray-400">{photo.lens_model}</p>}
            </InfoSection>
          )}

          {/* Exposure */}
          {(photo.f_number || photo.exposure_time || photo.iso || photo.focal_length) && (
            <InfoSection title="Exposure">
              <div className="grid grid-cols-2 gap-2 text-sm">
                {photo.f_number && (
                  <div>
                    <span className="text-gray-400">f/</span>
                    {photo.f_number}
                  </div>
                )}
                {photo.exposure_time && (
                  <div>
                    <span className="text-gray-400">Shutter: </span>
                    {photo.exposure_time}
                  </div>
                )}
                {photo.iso && (
                  <div>
                    <span className="text-gray-400">ISO </span>
                    {photo.iso}
                  </div>
                )}
                {photo.focal_length && (
                  <div>
                    <span className="text-gray-400">FL: </span>
                    {photo.focal_length}mm
                  </div>
                )}
              </div>
            </InfoSection>
          )}

          {/* Dimensions */}
          <InfoSection title="Details">
            <div className="space-y-1 text-sm">
              {photo.width && photo.height && (
                <p>{photo.width} × {photo.height}</p>
              )}
              <p>{formatFileSize(photo.file_size)}</p>
              <p className="text-gray-400">{photo.mime_type}</p>
            </div>
          </InfoSection>

          {/* Faces detected */}
          {photoFaces.length > 0 && (
            <InfoSection title={`Faces (${photoFaces.length})`}>
              <div className="space-y-3">
                {photoFaces.map((face) => {
                  const person = people.find((p) => p.id === face.person_id);
                  const isAssigning = assigningFaceId === face.id;
                  return (
                    <div key={face.id} className="rounded-lg bg-gray-800 p-2">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 flex-shrink-0 overflow-hidden rounded-full bg-gray-700">
                          <AuthImage
                            src={getFaceThumbnailUrl(face.id, 80)}
                            alt="Face"
                            className="h-full w-full object-cover"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-200 truncate">
                            {person?.name || 'Unnamed'}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(face.confidence * 100).toFixed(0)}% confidence
                          </p>
                        </div>
                        <button
                          onClick={() => { setAssigningFaceId(isAssigning ? null : face.id); setNewPersonName(''); }}
                          className="rounded px-2 py-1 text-xs text-primary-400 hover:bg-gray-700"
                        >
                          {isAssigning ? 'Cancel' : person ? 'Change' : 'Name'}
                        </button>
                      </div>

                      {/* Assign dropdown */}
                      {isAssigning && (
                        <div className="mt-2 space-y-2">
                          {/* Create new person */}
                          <form
                            onSubmit={(e) => {
                              e.preventDefault();
                              if (newPersonName.trim()) {
                                assignMutation.mutate({ faceId: face.id, new_person_name: newPersonName.trim() });
                              }
                            }}
                            className="flex gap-1"
                          >
                            <input
                              value={newPersonName}
                              onChange={(e) => setNewPersonName(e.target.value)}
                              placeholder="Enter name..."
                              className="flex-1 rounded border border-gray-600 bg-gray-700 px-2 py-1 text-xs text-white placeholder-gray-400 focus:border-primary-500 focus:outline-none"
                              autoFocus
                            />
                            <button
                              type="submit"
                              disabled={!newPersonName.trim() || assignMutation.isPending}
                              className="rounded bg-primary-600 px-2 py-1 text-xs text-white hover:bg-primary-700 disabled:opacity-50"
                            >
                              Add
                            </button>
                          </form>

                          {/* Or assign to existing person */}
                          {people.length > 0 && (
                            <div className="max-h-32 overflow-y-auto rounded border border-gray-700">
                              <p className="px-2 py-1 text-xs text-gray-500">Or assign to existing:</p>
                              {people
                                .filter((p) => p.id !== face.person_id)
                                .map((p) => (
                                  <button
                                    key={p.id}
                                    onClick={() => assignMutation.mutate({ faceId: face.id, person_id: p.id })}
                                    disabled={assignMutation.isPending}
                                    className="flex w-full items-center gap-2 px-2 py-1.5 text-xs text-gray-200 hover:bg-gray-700 disabled:opacity-50"
                                  >
                                    <span className="truncate">{p.name || `Person (${p.face_count} faces)`}</span>
                                  </button>
                                ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </InfoSection>
          )}

          {/* Add to Album */}
          <InfoSection title="Albums">
            <div className="relative">
              <button
                onClick={() => setShowAlbumPicker(!showAlbumPicker)}
                className="flex w-full items-center gap-2 rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add to Album
              </button>
              {showAlbumPicker && (
                <div className="mt-2 max-h-48 overflow-y-auto rounded-lg bg-gray-800 border border-gray-700">
                  {albums.length === 0 ? (
                    <p className="px-3 py-2 text-xs text-gray-400">No albums yet</p>
                  ) : (
                    albums.map((album) => (
                      <button
                        key={album.id}
                        onClick={() => addToAlbumMutation.mutate(album.id)}
                        disabled={addToAlbumMutation.isPending}
                        className="flex w-full items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 disabled:opacity-50"
                      >
                        <span>📁</span>
                        <span className="truncate">{album.name}</span>
                        <span className="ml-auto text-xs text-gray-500">{album.photo_count}</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </InfoSection>

          {/* Thumbnail preview */}
          <InfoSection title="Thumbnail">
            <div className="h-24 w-24 overflow-hidden rounded-lg">
              <AuthImage
                src={getThumbnailUrl(photo.id, 'sm')}
                alt="thumb"
                className="h-full w-full object-cover"
              />
            </div>
          </InfoSection>
        </aside>
      )}
    </div>
  );
}

function InfoSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-gray-500">{title}</h3>
      {children}
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function lonToTile(lon: number, zoom: number): number {
  return Math.floor(((lon + 180) / 360) * Math.pow(2, zoom));
}

function latToTile(lat: number, zoom: number): number {
  return Math.floor(
    ((1 - Math.log(Math.tan((lat * Math.PI) / 180) + 1 / Math.cos((lat * Math.PI) / 180)) / Math.PI) / 2) *
      Math.pow(2, zoom),
  );
}
