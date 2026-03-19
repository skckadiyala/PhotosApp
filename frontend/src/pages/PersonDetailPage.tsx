import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { usePerson, usePersonPhotos } from '../hooks/useFaces';
import { useScrollRestore } from '../hooks/useScrollRestore';
import { renamePerson, assignFace, getFaceThumbnailUrl } from '../api/faces';
import PhotoCard from '../components/photos/PhotoCard';
import FaceThumbnail from '../components/photos/FaceThumbnail';
import AuthImage from '../components/common/AuthImage';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import toast from 'react-hot-toast';

export default function PersonDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: person, isLoading: personLoading } = usePerson(id);
  const { data: photos, isLoading: photosLoading } = usePersonPhotos(id);

  useScrollRestore('photo', photosLoading);
  const [editing, setEditing] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [showFaces, setShowFaces] = useState(false);

  const renameMutation = useMutation({
    mutationFn: () => renamePerson(id!, nameInput),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['person', id] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      setEditing(false);
      toast.success('Name updated');
    },
    onError: () => toast.error('Failed to update name'),
  });

  const removeFaceMutation = useMutation({
    mutationFn: (faceId: string) => assignFace(faceId, { new_person_name: 'Removed' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['person', id] });
      queryClient.invalidateQueries({ queryKey: ['personPhotos', id] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
      queryClient.invalidateQueries({ queryKey: ['faces'] });
      toast.success('Face removed from this person');
    },
    onError: () => toast.error('Failed to remove face'),
  });

  if (personLoading) return <Spinner />;
  if (!person) return <EmptyState title="Person not found" icon="👤" />;

  const handleEditStart = () => {
    setNameInput(person.name || '');
    setEditing(true);
  };

  const handleSave = () => {
    if (nameInput.trim()) renameMutation.mutate();
  };

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center gap-4">
        <button
          onClick={() => navigate('/people')}
          className="rounded-lg p-2 text-gray-500 hover:bg-gray-100"
        >
          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>

        <FaceThumbnail personId={person.id} representativeFaceId={person.representative_face_id} size={64} />

        <div className="flex-1">
          {editing ? (
            <div className="flex items-center gap-2">
              <input
                value={nameInput}
                onChange={(e) => setNameInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                className="rounded-lg border border-gray-300 px-3 py-1.5 text-lg font-semibold focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
                autoFocus
              />
              <button
                onClick={handleSave}
                disabled={renameMutation.isPending}
                className="rounded-lg bg-primary-600 px-3 py-1.5 text-sm text-white hover:bg-primary-700"
              >
                Save
              </button>
              <button
                onClick={() => setEditing(false)}
                className="rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold text-gray-900">
                {person.name || 'Unnamed Person'}
              </h1>
              <button
                onClick={handleEditStart}
                className="rounded-lg p-1 text-gray-400 hover:text-gray-600"
                title="Rename"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
            </div>
          )}
          <p className="text-sm text-gray-500">{person.face_count} photos</p>
        </div>

        <button
          onClick={() => setShowFaces(!showFaces)}
          className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            showFaces
              ? 'bg-primary-100 text-primary-700'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
          title="Review & correct face assignments"
        >
          Review Faces
        </button>
      </div>

      {/* Face review section */}
      {showFaces && person.faces && person.faces.length > 0 && (
        <div className="mb-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <p className="mb-3 text-sm text-gray-600">
            Remove any incorrectly assigned faces. They will be moved to a separate group.
          </p>
          <div className="flex flex-wrap gap-3">
            {person.faces.map((face) => (
              <div key={face.id} className="group relative">
                <div className="h-16 w-16 overflow-hidden rounded-full bg-gray-200 ring-2 ring-gray-200 group-hover:ring-red-300 transition-all">
                  <AuthImage
                    src={getFaceThumbnailUrl(face.id, 128)}
                    alt="Face"
                    className="h-full w-full object-cover"
                  />
                </div>
                <button
                  onClick={() => removeFaceMutation.mutate(face.id)}
                  disabled={removeFaceMutation.isPending}
                  className="absolute -right-1 -top-1 hidden rounded-full bg-red-500 p-0.5 text-white shadow hover:bg-red-600 group-hover:block disabled:opacity-50"
                  title="Remove this face"
                >
                  <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Photos grid */}
      {photosLoading ? (
        <Spinner />
      ) : !photos || photos.length === 0 ? (
        <EmptyState title="No photos" description="No photos found for this person" />
      ) : (
        <div className="grid grid-cols-3 gap-1 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
          {photos.map((photo) => (
            <div key={photo.id} id={`photo-${photo.id}`}>
              <PhotoCard
                photo={photo}
                onClick={() => navigate(`/photo/${photo.id}`, {
                    state: { photoIds: photos.map((p) => p.id), returnTo: `/people/${id}` },
                  })}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
