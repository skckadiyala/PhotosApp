export interface Photo {
  id: string;
  file_name: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  taken_at: string | null;
  is_favorite: boolean;
  thumb_sm: string | null;
  thumb_md: string | null;
}

export interface PhotoDetail extends Photo {
  file_path: string;
  file_size: number;
  file_hash: string | null;
  camera_make: string | null;
  camera_model: string | null;
  lens_model: string | null;
  f_number: number | null;
  exposure_time: string | null;
  iso: number | null;
  focal_length: number | null;
  orientation: number | null;
  gps_latitude: number | null;
  gps_longitude: number | null;
  location_name: string | null;
  is_hidden: boolean;
  is_processed: boolean;
  thumb_lg: string | null;
  created_at: string;
  updated_at: string;
}
