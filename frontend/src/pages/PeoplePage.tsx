import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { usePeople } from '../hooks/useFaces';
import { fetchConfirmCount } from '../api/faces';
import Spinner from '../components/common/Spinner';
import EmptyState from '../components/common/EmptyState';
import FaceThumbnail from '../components/photos/FaceThumbnail';
import type { Person } from '../types/face';

export default function PeoplePage() {
  const { data, isLoading } = usePeople();
  const { data: confirmCount } = useQuery({ queryKey: ['faces-confirm-count'], queryFn: fetchConfirmCount });
  const navigate = useNavigate();

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
        <h1 className="text-xl font-semibold text-gray-900">People</h1>
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
      </div>
      <div className="grid grid-cols-3 gap-6 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
        {people.map((person) => (
          <button
            key={person.id}
            onClick={() => navigate(`/people/${person.id}`)}
            className="group flex flex-col items-center text-center"
          >
            <FaceThumbnail personId={person.id} size={96} />
            {person.name && (
              <p className="mt-2 text-sm font-medium text-gray-900 group-hover:text-primary-600 truncate max-w-[96px]">
                {person.name}
              </p>
            )}
            <p className="text-xs text-gray-500">{person.face_count} photos</p>
          </button>
        ))}
      </div>
    </div>
  );
}
