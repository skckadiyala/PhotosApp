import { useQuery } from '@tanstack/react-query';
import { fetchFaces, getFaceThumbnailUrl } from '../../api/faces';
import AuthImage from '../common/AuthImage';

interface Props {
  personId: string;
  size?: number;
}

/**
 * Shows a circular cropped face thumbnail for a person.
 */
export default function FaceThumbnail({ personId, size = 80 }: Props) {
  const { data: faces } = useQuery({
    queryKey: ['faces', { person_id: personId }],
    queryFn: () => fetchFaces({ person_id: personId, limit: 1 }),
    staleTime: 10 * 60 * 1000,
  });

  const face = faces?.[0];

  if (!face) {
    return (
      <div
        className="rounded-full bg-gray-200 flex items-center justify-center text-2xl"
        style={{ width: size, height: size }}
      >
        👤
      </div>
    );
  }

  return (
    <div
      className="overflow-hidden rounded-full ring-2 ring-transparent hover:ring-primary-400 transition-all bg-gray-200"
      style={{ width: size, height: size }}
    >
      <AuthImage
        src={getFaceThumbnailUrl(face.id, size * 2)}
        alt="Face"
        className="h-full w-full object-cover"
      />
    </div>
  );
}
