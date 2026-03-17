# PhotosApp — API Endpoint Reference

Base URL: `/api/v1`

All endpoints except `/auth/login` and `/auth/register` require a valid JWT in the `Authorization: Bearer <token>` header.

---

## Authentication

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/auth/register` | Create new user account | `{ username, email, password }` | `{ user, access_token, refresh_token }` |
| `POST` | `/auth/login` | Login with credentials | `{ email, password }` | `{ access_token, refresh_token }` |
| `POST` | `/auth/refresh` | Refresh access token | `{ refresh_token }` | `{ access_token }` |
| `POST` | `/auth/logout` | Invalidate refresh token | — | `204 No Content` |
| `GET`  | `/auth/me` | Get current user profile | — | `{ user }` |
| `PUT`  | `/auth/me` | Update profile | `{ username?, email?, password? }` | `{ user }` |

---

## Photos

| Method | Endpoint | Description | Query Params | Response |
|--------|----------|-------------|-------------|----------|
| `GET` | `/photos` | List photos (paginated) | `cursor`, `limit` (default 50), `sort` (date_desc/date_asc), `from_date`, `to_date` | `{ items: Photo[], next_cursor, total }` |
| `GET` | `/photos/:id` | Get single photo with full metadata | — | `{ Photo + location + tags + faces }` |
| `GET` | `/photos/:id/file` | Serve original photo file | — | Binary image file (`image/jpeg`) |
| `GET` | `/photos/:id/thumbnail/:size` | Serve thumbnail | `:size` = `sm` \| `md` \| `lg` | Binary image file |
| `DELETE` | `/photos/:id` | Hide photo (soft delete) | — | `204 No Content` |
| `PUT` | `/photos/:id` | Update photo metadata | `{ is_favorite?, is_hidden?, taken_at? }` | `{ Photo }` |
| `POST` | `/photos/:id/reprocess` | Re-run background processing | — | `{ job_id }` |
| `GET` | `/photos/stats` | Get library statistics | — | `{ total, by_year, by_month, by_camera }` |

---

## Thumbnails

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/thumbnails/:size/:path` | Serve thumbnail by cache path | Binary (served by Nginx in production) |

---

## Albums

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `GET` | `/albums` | List all albums | — | `{ items: Album[] }` |
| `POST` | `/albums` | Create new album | `{ name, description? }` | `{ Album }` |
| `GET` | `/albums/:id` | Get album with photos | `cursor`, `limit` | `{ Album, items: Photo[], next_cursor }` |
| `PUT` | `/albums/:id` | Update album | `{ name?, description?, cover_photo_id? }` | `{ Album }` |
| `DELETE` | `/albums/:id` | Delete album (not photos) | — | `204 No Content` |
| `POST` | `/albums/:id/photos` | Add photos to album | `{ photo_ids: UUID[] }` | `{ added: number }` |
| `DELETE` | `/albums/:id/photos` | Remove photos from album | `{ photo_ids: UUID[] }` | `204 No Content` |

### Smart Albums

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/albums/smart` | Create smart album | `{ name, rules: SmartRules }` | `{ Album }` |
| `PUT` | `/albums/:id/smart` | Update smart album rules | `{ rules: SmartRules }` | `{ Album }` |

---

## Faces & People

| Method | Endpoint | Description | Query Params | Response |
|--------|----------|-------------|-------------|----------|
| `GET` | `/people` | List all recognized people | `sort` (name/photo_count) | `{ items: Person[] }` |
| `GET` | `/people/:id` | Get person with their photos | `cursor`, `limit` | `{ Person, items: Photo[], next_cursor }` |
| `PUT` | `/people/:id` | Rename a person | `{ name }` | `{ Person }` |
| `POST` | `/people/merge` | Merge two people (same person) | `{ source_id, target_id }` | `{ Person }` |
| `DELETE` | `/people/:id` | Remove person grouping | — | `204 No Content` |
| `GET` | `/faces/unassigned` | Get faces not assigned to a person | `cursor`, `limit` | `{ items: Face[] }` |
| `PUT` | `/faces/:id` | Assign face to a person | `{ person_id }` | `{ Face }` |
| `GET` | `/faces/:id/thumbnail` | Get cropped face thumbnail | — | Binary image |
| `POST` | `/faces/recluster` | Trigger re-clustering of all faces | — | `{ job_id }` |

---

## Tags

| Method | Endpoint | Description | Query Params | Response |
|--------|----------|-------------|-------------|----------|
| `GET` | `/tags` | List all tags | `category` (object/scene/color/custom) | `{ items: Tag[] }` |
| `GET` | `/tags/:id/photos` | Get photos with a specific tag | `cursor`, `limit` | `{ Tag, items: Photo[], next_cursor }` |
| `POST` | `/photos/:id/tags` | Add manual tag to photo | `{ name }` | `{ Tag }` |
| `DELETE` | `/photos/:id/tags/:tag_id` | Remove tag from photo | — | `204 No Content` |

---

## Favorites

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/favorites` | List favorite photos | `{ items: Photo[], next_cursor }` |
| `POST` | `/photos/:id/favorite` | Mark as favorite | `{ Photo }` |
| `DELETE` | `/photos/:id/favorite` | Remove from favorites | `204 No Content` |

---

## Search

| Method | Endpoint | Description | Query Params | Response |
|--------|----------|-------------|-------------|----------|
| `GET` | `/search` | Universal search | `q` (text query), `type` (all/photo/person/album/tag), `from_date`, `to_date`, `location`, `person_id`, `tag`, `camera`, `cursor`, `limit` | `{ items: SearchResult[], next_cursor, facets }` |
| `GET` | `/search/suggestions` | Autocomplete suggestions | `q` (partial query) | `{ suggestions: string[] }` |

### Search Query Examples
- `q=beach` — Search tags, locations, filenames for "beach"
- `q=Paris 2024` — Photos in Paris taken in 2024
- `person_id=uuid&from_date=2024-01-01` — Specific person after Jan 2024
- `tag=sunset&location=California` — Sunset photos in California

---

## Map

| Method | Endpoint | Description | Query Params | Response |
|--------|----------|-------------|-------------|----------|
| `GET` | `/map/clusters` | Get clustered photo markers | `bounds` (sw_lat,sw_lng,ne_lat,ne_lng), `zoom` | `{ clusters: MapCluster[] }` |
| `GET` | `/map/photos` | Get photos at specific location | `lat`, `lng`, `radius` (meters), `limit` | `{ items: Photo[] }` |
| `GET` | `/map/heatmap` | Get photo density heatmap data | `bounds` | `{ points: [lat, lng, weight][] }` |

### MapCluster Schema
```json
{
    "lat": 48.8566,
    "lng": 2.3522,
    "count": 42,
    "preview_photo_id": "uuid",
    "location_label": "Paris, France"
}
```

---

## Jobs / Processing Status

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/jobs/status` | Get background processing status | `{ pending, processing, completed, failed, queue_sizes }` |
| `GET` | `/jobs/:id` | Get specific job status | `{ job_id, status, progress, result? }` |
| `POST` | `/jobs/scan` | Trigger full library scan | `{ job_id }` |

---

## Admin (admin role only)

| Method | Endpoint | Description | Response |
|--------|----------|-------------|----------|
| `GET` | `/admin/users` | List all users | `{ items: User[] }` |
| `PUT` | `/admin/users/:id` | Update user role | `{ User }` |
| `DELETE` | `/admin/users/:id` | Delete user | `204 No Content` |
| `GET` | `/admin/system` | System info (disk, DB size, etc.) | `{ SystemInfo }` |
| `POST` | `/admin/reindex` | Rebuild search index | `{ job_id }` |

---

## WebSocket

| Endpoint | Description |
|----------|-------------|
| `WS /ws/events` | Real-time events: new photos detected, processing complete, face clusters updated |

### Event Types
```json
{ "type": "photo:new",        "data": { "photo_id": "uuid" } }
{ "type": "photo:processed",  "data": { "photo_id": "uuid", "tasks": ["thumbnail", "metadata", "faces", "tags"] } }
{ "type": "face:clustered",   "data": { "person_id": "uuid", "face_count": 5 } }
{ "type": "job:progress",     "data": { "job_id": "uuid", "progress": 0.75 } }
{ "type": "scan:complete",    "data": { "new_photos": 150, "duration_ms": 30000 } }
```

---

## Common Response Formats

### Pagination (Cursor-based)
```json
{
    "items": [],
    "next_cursor": "eyJpZCI6MTAwfQ==",
    "total": 5000
}
```

### Error Response
```json
{
    "error": {
        "code": "NOT_FOUND",
        "message": "Photo not found",
        "details": {}
    }
}
```

### HTTP Status Codes
| Code | Usage |
|------|-------|
| `200` | Success |
| `201` | Created |
| `204` | No Content (successful delete) |
| `400` | Bad Request (validation error) |
| `401` | Unauthorized (missing/invalid token) |
| `403` | Forbidden (insufficient role) |
| `404` | Not Found |
| `409` | Conflict (duplicate) |
| `429` | Rate Limited |
| `500` | Internal Server Error |
