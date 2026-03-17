# PhotosApp — System Architecture

## Overview

PhotosApp is a self-hosted photo management application similar to Google Photos. It connects directly to photos stored on an external drive, provides face detection/recognition, location-based browsing, smart albums, AI auto-tagging, and a modern responsive UI. It is accessible securely from anywhere via Cloudflare Tunnel.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            INTERNET                                     │
│                                                                         │
│   Browser/Mobile ◄──── HTTPS ────► Cloudflare Tunnel (cloudflared)      │
│                                          │                              │
└──────────────────────────────────────────┼──────────────────────────────┘
                                           │
┌──────────────────────────────────────────┼──────────────────────────────┐
│                        DOCKER NETWORK (photosapp_net)                   │
│                                          │                              │
│  ┌───────────────────────────────────────┼────────────────────────┐     │
│  │                    Nginx Reverse Proxy (port 80)               │     │
│  │               Serves frontend + proxies /api/* to backend      │     │
│  └────────┬──────────────────────────────┬────────────────────────┘     │
│           │                              │                              │
│           ▼                              ▼                              │
│  ┌─────────────────┐          ┌─────────────────────┐                  │
│  │   React SPA     │          │   FastAPI Backend    │                  │
│  │  (Static Build) │          │   (Python 3.12)      │                  │
│  │                 │          │   Port 8000           │                  │
│  │  - Photo Grid   │          │                       │                  │
│  │  - Face Albums  │          │  - REST API           │                  │
│  │  - Map View     │          │  - Auth (JWT)         │                  │
│  │  - Search       │          │  - File Serving       │                  │
│  │  - Lightbox     │          │  - WebSocket (live)   │                  │
│  └─────────────────┘          └──────────┬────────────┘                  │
│                                          │                              │
│                          ┌───────────────┼───────────────┐              │
│                          │               │               │              │
│                          ▼               ▼               ▼              │
│                  ┌──────────┐   ┌──────────────┐  ┌───────────┐        │
│                  │  Redis   │   │ PostgreSQL   │  │  External │        │
│                  │  7.x     │   │ 16 + pgvector│  │  Drive    │        │
│                  │          │   │              │  │ (read-only)│        │
│                  │ - Queue  │   │ - Metadata   │  │ /mnt/photos│       │
│                  │ - Cache  │   │ - Embeddings │  └───────────┘        │
│                  │ - Pub/Sub│   │ - Users      │                       │
│                  └────┬─────┘   └──────────────┘                       │
│                       │                                                 │
│                       ▼                                                 │
│              ┌─────────────────────────────────┐                       │
│              │     Celery Workers (Python)      │                       │
│              │                                  │                       │
│              │  Worker Queues:                   │                       │
│              │  ┌─────────────────────────────┐ │                       │
│              │  │ thumbnails — Generate multi- │ │                       │
│              │  │   resolution thumbnails      │ │                       │
│              │  ├─────────────────────────────┤ │                       │
│              │  │ metadata — EXIF extraction,  │ │                       │
│              │  │   GPS reverse geocoding      │ │                       │
│              │  ├─────────────────────────────┤ │                       │
│              │  │ faces — Detection, embedding,│ │                       │
│              │  │   clustering (DBSCAN)        │ │                       │
│              │  ├─────────────────────────────┤ │                       │
│              │  │ tagging — AI scene/object    │ │                       │
│              │  │   classification (CLIP/BLIP) │ │                       │
│              │  └─────────────────────────────┘ │                       │
│              │                                  │                       │
│              │  Models:                          │                       │
│              │  - face_recognition (dlib/InsightFace) │                  │
│              │  - CLIP (OpenAI) for auto-tagging│                       │
│              │  - Pillow/libvips for thumbnails  │                       │
│              └──────────────────────────────────┘                       │
│                                                                         │
│              ┌──────────────────────────────────┐                       │
│              │   File Watcher (watchdog)         │                       │
│              │   Monitors /mnt/photos for new    │                       │
│              │   files → dispatches Celery tasks  │                       │
│              └──────────────────────────────────┘                       │
│                                                                         │
│              ┌──────────────────────────────────┐                       │
│              │   Thumbnail Cache Volume          │                       │
│              │   /data/thumbnails/               │                       │
│              │   ├── sm/ (200px)                 │                       │
│              │   ├── md/ (800px)                 │                       │
│              │   └── lg/ (1920px)                │                       │
│              └──────────────────────────────────┘                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### 1. Photo Ingestion Pipeline
```
External Drive ──► File Watcher (watchdog)
                        │
                        ▼
                   Celery Dispatch
                        │
          ┌─────────────┼─────────────────┐
          ▼             ▼                 ▼
     [metadata]     [thumbnails]      [faces]
          │             │                 │
          ▼             ▼                 ▼
    EXIF extract   Generate 3 sizes   Detect faces
    GPS → geocode  sm/md/lg           Extract 128d embeddings
          │             │                 │
          ▼             ▼                 ▼
    PostgreSQL     Filesystem cache   pgvector + DBSCAN cluster
          │                               │
          ▼                               ▼
     [tagging]                      Group into People
          │
          ▼
    CLIP/BLIP scene & object tags → PostgreSQL
```

### 2. Request Flow (User browses photos)
```
Browser → Cloudflare Tunnel → Nginx → FastAPI
                                         │
           ┌─────────────────────────────┤
           ▼                             ▼
    Serve thumbnail              Query PostgreSQL
    from cache                   (metadata, faces, tags)
           │                             │
           ▼                             ▼
    Return image bytes           Return JSON response
```

### 3. Face Recognition Flow
```
New Photo → face_recognition.face_locations() → Detect bounding boxes
         → face_recognition.face_encodings()  → 128-dim vector per face
         → Store in pgvector (faces table)
         → DBSCAN clustering on all embeddings
         → Assign cluster_id → maps to People
         → User can rename Person via UI
```

---

## Technology Stack

| Layer | Technology | Justification |
|-------|-----------|---------------|
| **Backend API** | Python 3.12 + FastAPI | Async, fast, excellent ML/CV library ecosystem (face_recognition, CLIP, Pillow). Type hints + auto OpenAPI docs. |
| **Task Queue** | Celery 5.x + Redis | Mature, battle-tested. Supports priority queues, retries, rate limiting. Perfect for CPU-heavy ML tasks. |
| **Database** | PostgreSQL 16 + pgvector | Relational integrity for metadata. pgvector enables similarity search on face embeddings without external vector DB. |
| **Cache/Broker** | Redis 7.x | Message broker for Celery + response caching + pub/sub for real-time updates. |
| **Face Detection** | InsightFace (or dlib via face_recognition) | InsightFace: state-of-art accuracy, GPU optional. face_recognition: simpler API, CPU-friendly. |
| **Auto-Tagging** | OpenAI CLIP (via open_clip) | Zero-shot image classification. No training needed. Tags scenes, objects, colors from natural language prompts. |
| **Thumbnails** | Pillow + libvips | libvips is 8x faster than Pillow for resizing. Pillow as fallback. |
| **EXIF Parsing** | exifread + piexif | Pure Python, handles all EXIF/IPTC/XMP metadata including GPS. |
| **Geocoding** | Reverse geocoding via local Nominatim or geopy | Convert GPS coordinates to city/country. Local Nominatim for privacy. |
| **File Watching** | watchdog | Cross-platform filesystem event monitoring. |
| **Frontend** | React 18 + TypeScript + Vite | Fast dev experience, strong typing, massive ecosystem. |
| **UI Components** | Tailwind CSS + Radix UI | Utility-first CSS + accessible headless components. |
| **Photo Grid** | react-photo-album | Masonry/justified layout optimized for photo galleries. |
| **Map** | Leaflet + react-leaflet | Free, open-source map. No API key required. OpenStreetMap tiles. |
| **State Management** | TanStack Query (React Query) | Server-state caching, pagination, infinite scroll support. |
| **Auth** | JWT (PyJWT) + bcrypt | Stateless auth tokens. bcrypt for password hashing. |
| **Reverse Proxy** | Nginx | Serves static frontend, proxies API, handles compression/caching. |
| **Remote Access** | Cloudflare Tunnel (cloudflared) | Free, no port forwarding, automatic HTTPS, DDoS protection. |
| **Containerization** | Docker + Docker Compose | Reproducible deployment. Isolates services. Easy volume mounting. |

---

## Security Considerations

1. **External drive mounted read-only** — App never modifies original photos
2. **JWT tokens with short expiry** (15min access + 7d refresh)
3. **Bcrypt password hashing** with salt rounds = 12
4. **CORS restricted** to frontend origin only
5. **Rate limiting** on auth endpoints (5 attempts/min)
6. **Cloudflare Tunnel** — No exposed ports, encrypted tunnel
7. **Input validation** via Pydantic models on all endpoints
8. **SQL injection prevention** via SQLAlchemy ORM (parameterized queries)
9. **Path traversal protection** — Validate all file paths against allowed base directory
10. **Thumbnail serving** — Dedicated endpoint, no arbitrary file access

---

## Scalability Notes

- **Workers scale horizontally**: Run multiple Celery workers for faster processing
- **Separate queues**: Thumbnail generation (fast) doesn't block face detection (slow)
- **Thumbnail caching**: Generated once, served directly by Nginx
- **Database indexing**: GIN indexes on tags, B-tree on dates, HNSW on face vectors
- **Lazy processing**: Only process photos on demand or in background batches
- **Pagination**: All list endpoints paginated (cursor-based for infinite scroll)
