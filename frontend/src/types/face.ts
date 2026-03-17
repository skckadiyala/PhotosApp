export interface Face {
  id: string;
  photo_id: string;
  person_id: string | null;
  bbox_top: number;
  bbox_right: number;
  bbox_bottom: number;
  bbox_left: number;
  confidence: number;
  match_distance: number;
  status: 'confirmed' | 'pending' | 'rejected';
  created_at: string;
}

export interface Person {
  id: string;
  name: string | null;
  face_count: number;
  created_at: string;
  updated_at: string;
}

export interface PersonDetail extends Person {
  faces: Face[];
}
