import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchFacesToConfirm, confirmFace, getFaceThumbnailUrl, assignFace, deleteFace } from '../api/faces';
import type { FaceConfirmItem } from '../api/faces';
import AuthImage from '../components/common/AuthImage';
import Spinner from '../components/common/Spinner';
import toast from 'react-hot-toast';

export default function FaceConfirmPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showNameInput, setShowNameInput] = useState(false);
  const [newName, setNewName] = useState('');

  const { data: faces, isLoading } = useQuery({
    queryKey: ['faces-confirm'],
    queryFn: () => fetchFacesToConfirm(100),
  });

  const confirmMutation = useMutation({
    mutationFn: ({ faceId, accept }: { faceId: string; accept: boolean }) =>
      confirmFace(faceId, accept),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['faces-confirm'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
    },
  });

  const reassignMutation = useMutation({
    mutationFn: ({ faceId, name }: { faceId: string; name: string }) =>
      assignFace(faceId, { new_person_name: name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['faces-confirm'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (faceId: string) => deleteFace(faceId),
    onSuccess: () => {
      toast.success('Removed bad detection');
      queryClient.invalidateQueries({ queryKey: ['faces-confirm'] });
      queryClient.invalidateQueries({ queryKey: ['people'] });
    },
  });

  const items: FaceConfirmItem[] = faces ?? [];
  const current = items[currentIndex];

  // Reset index if items change (e.g., after mutation)
  useEffect(() => {
    if (currentIndex >= items.length) {
      setCurrentIndex(Math.max(0, items.length - 1));
    }
  }, [items.length, currentIndex]);

  function handleConfirm(accept: boolean) {
    if (!current) return;
    confirmMutation.mutate(
      { faceId: current.id, accept },
      { onSuccess: () => advance() }
    );
  }

  function handleReassign() {
    if (!current || !newName.trim()) return;
    reassignMutation.mutate(
      { faceId: current.id, name: newName.trim() },
      {
        onSuccess: () => {
          toast.success(`Assigned to "${newName.trim()}"`);
          setNewName('');
          setShowNameInput(false);
          advance();
        },
      }
    );
  }

  function advance() {
    // Stay at same index since the item will be removed from the list after refetch
    // If we're at the end, go back
    if (currentIndex >= items.length - 1) {
      setCurrentIndex(Math.max(0, currentIndex - 1));
    }
  }

  if (isLoading) return <Spinner />;

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="text-5xl mb-4">✅</div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">All caught up!</h2>
        <p className="text-gray-500 mb-6">No faces need your review right now.</p>
        <button
          onClick={() => navigate('/people')}
          className="rounded-lg bg-primary-600 px-4 py-2 text-white hover:bg-primary-700"
        >
          Back to People
        </button>
      </div>
    );
  }

  const personLabel = current.person_name || 'this person';
  const busy = confirmMutation.isPending || reassignMutation.isPending || deleteMutation.isPending;

  return (
    <div className="mx-auto max-w-lg py-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <button
          onClick={() => navigate('/people')}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          ← Back to People
        </button>
        <span className="text-sm text-gray-500">
          {currentIndex + 1} of {items.length} faces to review
        </span>
      </div>

      {/* Card */}
      <div className="rounded-2xl bg-white shadow-lg overflow-hidden">
        {/* Question */}
        <div className="px-6 pt-5 pb-3 text-center">
          <p className="text-lg font-medium text-gray-900">
            Is this <span className="text-primary-600">{personLabel}</span>?
          </p>
        </div>

        {/* Faces comparison */}
        <div className="flex items-center justify-center gap-8 px-6 py-4">
          {/* The face being reviewed */}
          <div className="flex flex-col items-center">
            <div className="h-32 w-32 overflow-hidden rounded-full ring-2 ring-amber-400">
              <AuthImage
                src={getFaceThumbnailUrl(current.id, 256)}
                alt="Face to review"
                className="h-full w-full object-cover"
              />
            </div>
            <span className="mt-2 text-xs text-gray-400">This face</span>
          </div>

          {/* Arrow */}
          <div className="text-2xl text-gray-300">→</div>

          {/* Reference face (confirmed face from same person) */}
          <div className="flex flex-col items-center">
            {current.reference_face_id ? (
              <div className="h-32 w-32 overflow-hidden rounded-full ring-2 ring-green-400">
                <AuthImage
                  src={getFaceThumbnailUrl(current.reference_face_id, 256)}
                  alt={personLabel}
                  className="h-full w-full object-cover"
                />
              </div>
            ) : (
              <div className="flex h-32 w-32 items-center justify-center rounded-full bg-gray-100 ring-2 ring-green-400 text-4xl">
                👤
              </div>
            )}
            <span className="mt-2 text-xs text-gray-500 font-medium">
              {personLabel}
            </span>
          </div>
        </div>

        {/* Distance indicator */}
        <div className="px-6 pb-2 text-center">
          <span className="text-xs text-gray-400">
            Match distance: {current.match_distance.toFixed(3)}
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex gap-3 px-6 pb-4 pt-2">
          <button
            onClick={() => handleConfirm(true)}
            disabled={busy}
            className="flex-1 rounded-xl bg-green-500 py-3 text-base font-semibold text-white hover:bg-green-600 disabled:opacity-50 transition-colors"
          >
            Yes
          </button>
          <button
            onClick={() => handleConfirm(false)}
            disabled={busy}
            className="flex-1 rounded-xl bg-red-500 py-3 text-base font-semibold text-white hover:bg-red-600 disabled:opacity-50 transition-colors"
          >
            No
          </button>
        </div>

        {/* "Not a face" delete option */}
        <div className="px-6 pb-2">
          <button
            onClick={() => current && deleteMutation.mutate(current.id)}
            disabled={busy}
            className="w-full text-center text-xs text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
          >
            🗑 Not a face / bad detection — remove
          </button>
        </div>

        {/* "Someone else" option */}
        <div className="border-t px-6 py-3">
          {!showNameInput ? (
            <button
              onClick={() => setShowNameInput(true)}
              className="w-full text-center text-sm text-primary-600 hover:text-primary-700"
            >
              This is someone else...
            </button>
          ) : (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleReassign()}
                placeholder="Type a name..."
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
                autoFocus
              />
              <button
                onClick={handleReassign}
                disabled={busy || !newName.trim()}
                className="rounded-lg bg-primary-600 px-3 py-2 text-sm text-white hover:bg-primary-700 disabled:opacity-50"
              >
                Save
              </button>
              <button
                onClick={() => { setShowNameInput(false); setNewName(''); }}
                className="text-sm text-gray-400 hover:text-gray-600"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Navigation between faces */}
      {items.length > 1 && (
        <div className="mt-4 flex items-center justify-center gap-4">
          <button
            onClick={() => setCurrentIndex(Math.max(0, currentIndex - 1))}
            disabled={currentIndex === 0}
            className="rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200 disabled:opacity-40"
          >
            ← Previous
          </button>
          <button
            onClick={() => setCurrentIndex(Math.min(items.length - 1, currentIndex + 1))}
            disabled={currentIndex >= items.length - 1}
            className="rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200 disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
