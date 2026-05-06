import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { usePeople } from '../hooks/useFaces';
import { fetchConfirmCount, mergePeople } from '../api/faces';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import FaceThumbnail from '../components/photos/FaceThumbnail';
import type { Person } from '../types/face';

const LONG_PRESS_MS = 500;

export default function PeoplePage() {
  const { data, isLoading } = usePeople();
  const { data: confirmCount } = useQuery({ queryKey: ['faces-confirm-count'], queryFn: fetchConfirmCount });
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Multi-select state — ordered array so we know the merge target (first selected)
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [mergeMode, setMergeMode] = useState(false);
  const [merging, setMerging] = useState(false);

  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const didLongPress = useRef(false);

  const enterMergeMode = useCallback((id: string) => {
    setMergeMode(true);
    setSelectedIds([id]);
  }, []);

  const cancelMerge = useCallback(() => {
    setMergeMode(false);
    setSelectedIds([]);
  }, []);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      return [...prev, id];
    });
  }, []);

  const handlePointerDown = useCallback(
    (id: string) => {
      if (mergeMode) return;
      didLongPress.current = false;
      longPressTimer.current = setTimeout(() => {
        didLongPress.current = true;
        enterMergeMode(id);
      }, LONG_PRESS_MS);
    },
    [mergeMode, enterMergeMode],
  );

  const handlePointerUp = useCallback(() => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  }, []);

  const handleClick = useCallback(
    (person: Person) => {
      if (didLongPress.current) {
        didLongPress.current = false;
        return;
      }
      if (mergeMode) {
        toggleSelect(person.id);
        return;
      }
      navigate(`/people/${person.id}`);
    },
    [mergeMode, toggleSelect, navigate],
  );

  const handleMerge = useCallback(async () => {
    if (selectedIds.length < 2) return;
    const [targetId, ...sourceIds] = selectedIds;
    setMerging(true);
    try {
      await mergePeople(targetId, sourceIds);
      await queryClient.invalidateQueries({ queryKey: ['people'] });
      cancelMerge();
    } finally {
      setMerging(false);
    }
  }, [selectedIds, queryClient, cancelMerge]);

  if (isLoading) return <Spinner />;

  const people: Person[] = data ?? [];

  if (people.length === 0)
    return (
      <EmptyState
        title="No people detected yet"
        description="Run face detection to find people in your photos"
        icon="👤"
      />
    );

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-gray-900">
          {mergeMode ? `Select people to merge (${selectedIds.length} selected)` : 'People'}
        </h1>
        <div className="flex items-center gap-3">
          {mergeMode ? (
            <button
              onClick={cancelMerge}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          ) : (
            <>
              {(confirmCount ?? 0) > 0 && (
                <button
                  onClick={() => navigate('/people/confirm')}
                  className="flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-100 transition-colors"
                >
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-amber-500 text-xs text-white font-bold">
                    {confirmCount}
                  </span>
                  Review faces
                </button>
              )}
              <button
                onClick={() => setMergeMode(true)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
              >
                Merge
              </button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
        {people.map((person) => {
          const isSelected = selectedIds.includes(person.id);
          const selectionIndex = selectedIds.indexOf(person.id);
          return (
            <button
              key={person.id}
              onClick={() => handleClick(person)}
              onPointerDown={() => handlePointerDown(person.id)}
              onPointerUp={handlePointerUp}
              onPointerLeave={handlePointerUp}
              className={`group relative flex flex-col items-center text-center transition-all ${
                mergeMode
                  ? isSelected
                    ? 'opacity-100'
                    : 'opacity-60'
                  : ''
              }`}
            >
              <div className={`relative rounded-full ${isSelected ? 'ring-4 ring-blue-500 ring-offset-2' : ''}`}>
                <FaceThumbnail personId={person.id} representativeFaceId={person.representative_face_id} size={96} />
                {isSelected && (
                  <div className="absolute -top-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-blue-500 text-xs font-bold text-white shadow">
                    {selectionIndex === 0 ? '★' : selectionIndex + 1}
                  </div>
                )}
              </div>
              {person.name && (
                <p className="mt-2 text-sm font-medium text-gray-900 group-hover:text-primary-600 truncate max-w-[96px]">
                  {person.name}
                </p>
              )}
              <p className="text-xs text-gray-500">{person.face_count} photos</p>
            </button>
          );
        })}
      </div>

      {mergeMode && selectedIds.length >= 2 && (
        <div className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full bg-gray-900 px-5 py-3 shadow-2xl">
          <span className="text-sm font-semibold text-white">
            Merge {selectedIds.length} people into first selected
          </span>
          <div className="h-4 w-px bg-white/30" />
          <button
            onClick={handleMerge}
            disabled={merging}
            className="text-sm font-medium text-blue-300 hover:text-blue-200 disabled:opacity-50 transition-colors"
          >
            {merging ? 'Merging…' : 'Merge'}
          </button>
          <div className="h-4 w-px bg-white/30" />
          <button
            onClick={cancelMerge}
            className="text-sm font-medium text-white hover:text-red-300 transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
