export interface Photo {
  id: string;
  file_name: string;
  mime_type: string;
  file_size: number | null;
  width: number | null;
  height: number | null;
  taken_at: string | null;
  is_favorite: boolean;
  thumb_sm: string | null;
  thumb_md: string | null;
}

export interface CoverPhotoInfo {
  id: string;
  thumb_sm?: string | null;
  thumb_md?: string | null;
}

export interface MonthSummary {
  year: number;
  month: number;
  key: string;       // e.g. "2024-12"
  label: string;     // e.g. "December 2024"
  count: number;
  cover_photos: CoverPhotoInfo[];
}

export interface YearSummary {
  year: number;
  count: number;
  cover_photo: CoverPhotoInfo | null;
  months: MonthSummary[];
}

export interface LibrarySummary {
  years: YearSummary[];
  total: number;
}

export interface MonthPhotosResponse {
  year: number;
  month: number;
  count: number;
  items: Photo[];
}

export interface EventClusterSummary {
  cluster_id: number;
  start_at: string;
  end_at: string;
  count: number;
  cover_photo: CoverPhotoInfo | null;
}

export interface EventClusterPhotosResponse {
  cluster_id: number;
  gap_hours: number;
  start_at: string | null;
  end_at: string | null;
  count: number;
  items: Photo[];
}

export interface PhotoDetail extends Photo {
  file_path: string;
  host_file_path: string | null;
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
