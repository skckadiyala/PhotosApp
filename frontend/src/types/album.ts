export interface Album {
  id: string;
  name: string;
  description: string | null;
  cover_photo_id: string | null;
  photo_count: number;
  created_at: string;
  updated_at: string;
}
