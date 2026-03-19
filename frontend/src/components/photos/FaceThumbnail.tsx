import { getFaceThumbnailUrl } from '../../api/faces';
import AuthImage from '../common/AuthImage';

interface Props {
  personId: string;
  representativeFaceId?: string | null;
  size?: number;
}

/**
 * Shows a circular cropped face thumbnail for a person.
 * Uses the representative_face_id (closest face to cluster centroid) when available.
 */
export default function FaceThumbnail({ representativeFaceId, size = 80 }: Props) {
  if (!representativeFaceId) {
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
        src={getFaceThumbnailUrl(representativeFaceId, size * 2)}
        alt="Face"
        className="h-full w-full object-cover"
      />
    </div>
  );
}
