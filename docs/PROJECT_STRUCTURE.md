# PhotosApp — Project Structure

```
PhotosApp/
│
├── docs/                              # Documentation
│   ├── ARCHITECTURE.md                # System architecture (this doc)
│   ├── PROJECT_STRUCTURE.md           # Folder structure (you are here)
│   ├── DATABASE_SCHEMA.md             # Database schema design
│   └── API_ENDPOINTS.md               # REST API endpoint reference
│
├── docker-compose.yml                 # Orchestrates all services
├── docker-compose.dev.yml             # Development overrides
├── .env.example                       # Environment variable template
├── Makefile                           # Common commands (make up, make down, etc.)
│
├── backend/                           # Python FastAPI backend
│   ├── Dockerfile                     # Multi-stage Python image
│   ├── pyproject.toml                 # Python dependencies (Poetry/pip)
│   ├── alembic.ini                    # Database migration config
│   ├── alembic/                       # Migration scripts
│   │   ├── env.py
│   │   └── versions/
│   │
│   └── app/                           # Application source
│       ├── __init__.py
│       ├── main.py                    # FastAPI app entry point
│       ├── config.py                  # Settings (from env vars)
│       │
│       ├── api/                       # API route handlers
│       │   ├── __init__.py
│       │   ├── deps.py                # Shared dependencies (get_db, get_current_user)
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── router.py          # Aggregate v1 router
│       │       ├── auth.py            # POST /auth/login, /auth/register, /auth/refresh
│       │       ├── photos.py          # GET/DELETE /photos, /photos/{id}
│       │       ├── albums.py          # CRUD /albums
│       │       ├── faces.py           # GET /faces, /people
│       │       ├── people.py          # CRUD /people (rename, merge)
│       │       ├── tags.py            # GET /tags
│       │       ├── search.py          # GET /search
│       │       ├── map.py             # GET /map/clusters, /map/photos
│       │       ├── favorites.py       # POST/DELETE /favorites
│       │       └── jobs.py            # GET /jobs/status (processing status)
│       │
│       ├── models/                    # SQLAlchemy ORM models
│       │   ├── __init__.py
│       │   ├── base.py               # Declarative base + mixins
│       │   ├── user.py
│       │   ├── photo.py
│       │   ├── album.py
│       │   ├── face.py
│       │   ├── person.py
│       │   ├── tag.py
│       │   └── location.py
│       │
│       ├── schemas/                   # Pydantic request/response schemas
│       │   ├── __init__.py
│       │   ├── auth.py
│       │   ├── photo.py
│       │   ├── album.py
│       │   ├── face.py
│       │   ├── person.py
│       │   ├── tag.py
│       │   ├── search.py
│       │   └── common.py             # Pagination, error responses
│       │
│       ├── services/                  # Business logic layer
│       │   ├── __init__.py
│       │   ├── photo_service.py
│       │   ├── album_service.py
│       │   ├── face_service.py
│       │   ├── search_service.py
│       │   └── auth_service.py
│       │
│       ├── workers/                   # Celery task definitions
│       │   ├── __init__.py
│       │   ├── celery_app.py          # Celery configuration
│       │   ├── tasks/
│       │   │   ├── __init__.py
│       │   │   ├── thumbnail.py       # Generate sm/md/lg thumbnails
│       │   │   ├── metadata.py        # EXIF extraction + geocoding
│       │   │   ├── faces.py           # Face detection + embedding
│       │   │   ├── clustering.py      # DBSCAN face clustering
│       │   │   └── tagging.py         # CLIP/BLIP auto-tagging
│       │   └── pipeline.py            # Orchestrates task chains per photo
│       │
│       ├── watcher/                   # File system watcher
│       │   ├── __init__.py
│       │   └── file_watcher.py        # watchdog-based directory monitor
│       │
│       ├── core/                      # Cross-cutting concerns
│       │   ├── __init__.py
│       │   ├── security.py            # JWT creation/validation, password hashing
│       │   ├── database.py            # SQLAlchemy engine + session factory
│       │   ├── redis.py               # Redis connection pool
│       │   └── exceptions.py          # Custom exception classes
│       │
│       └── utils/                     # Utility functions
│           ├── __init__.py
│           ├── image.py               # Image manipulation helpers
│           ├── exif.py                # EXIF parsing helpers
│           ├── geo.py                 # GPS coordinate utilities
│           └── path.py                # Safe path resolution
│
├── frontend/                          # React + TypeScript SPA
│   ├── Dockerfile                     # Multi-stage Node build → Nginx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── index.html
│   │
│   └── src/
│       ├── main.tsx                   # React entry point
│       ├── App.tsx                    # Root component + routing
│       ├── vite-env.d.ts
│       │
│       ├── api/                       # API client layer
│       │   ├── client.ts              # Axios instance + interceptors
│       │   ├── auth.ts
│       │   ├── photos.ts
│       │   ├── albums.ts
│       │   ├── faces.ts
│       │   ├── search.ts
│       │   └── map.ts
│       │
│       ├── hooks/                     # React Query hooks
│       │   ├── usePhotos.ts
│       │   ├── useAlbums.ts
│       │   ├── useFaces.ts
│       │   ├── useSearch.ts
│       │   ├── useMap.ts
│       │   └── useAuth.ts
│       │
│       ├── pages/                     # Route pages
│       │   ├── LoginPage.tsx
│       │   ├── PhotosPage.tsx         # Main photo grid
│       │   ├── AlbumsPage.tsx
│       │   ├── AlbumDetailPage.tsx
│       │   ├── PeoplePage.tsx         # Face clusters
│       │   ├── PersonDetailPage.tsx
│       │   ├── MapPage.tsx
│       │   ├── SearchPage.tsx
│       │   ├── FavoritesPage.tsx
│       │   └── SettingsPage.tsx
│       │
│       ├── components/                # Reusable UI components
│       │   ├── layout/
│       │   │   ├── AppShell.tsx       # Sidebar + header layout
│       │   │   ├── Sidebar.tsx
│       │   │   └── Header.tsx
│       │   ├── photos/
│       │   │   ├── PhotoGrid.tsx      # Masonry grid
│       │   │   ├── PhotoCard.tsx      # Single photo tile
│       │   │   ├── Lightbox.tsx       # Fullscreen viewer
│       │   │   └── MetadataPanel.tsx  # EXIF/location sidebar
│       │   ├── faces/
│       │   │   ├── FaceGrid.tsx
│       │   │   └── FaceChip.tsx
│       │   ├── map/
│       │   │   ├── PhotoMap.tsx
│       │   │   └── MapCluster.tsx
│       │   ├── albums/
│       │   │   ├── AlbumCard.tsx
│       │   │   └── AlbumCreateDialog.tsx
│       │   └── common/
│       │       ├── SearchBar.tsx
│       │       ├── Spinner.tsx
│       │       ├── EmptyState.tsx
│       │       └── ProgressiveImage.tsx  # Blur-up lazy loading
│       │
│       ├── stores/                    # Zustand or context stores
│       │   ├── authStore.ts
│       │   └── uiStore.ts            # Sidebar state, lightbox, etc.
│       │
│       ├── types/                     # TypeScript type definitions
│       │   ├── photo.ts
│       │   ├── album.ts
│       │   ├── face.ts
│       │   ├── person.ts
│       │   └── api.ts                # API response wrappers
│       │
│       └── lib/                       # Utilities
│           ├── constants.ts
│           ├── formatters.ts          # Date, file size formatting
│           └── mapUtils.ts
│
├── nginx/                             # Nginx configuration
│   ├── nginx.conf                     # Main config
│   └── default.conf                   # Server block (frontend + API proxy)
│
├── cloudflare/                        # Cloudflare Tunnel
│   └── config.yml                     # Tunnel configuration
│
└── scripts/                           # Utility scripts
    ├── init-db.sh                     # First-time DB setup
    ├── reprocess.py                   # Re-run processing on all photos
    └── backup-db.sh                   # PostgreSQL backup
```
