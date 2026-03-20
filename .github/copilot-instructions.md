---
applyTo: "**/*" 
description: "PhotosApp — self-hosted photo management with face recognition, GPS, albums, and search"
---

# PhotosApp — Workspace Instructions for AI Agents

## Quick Overview

**PhotosApp** is a self-hosted photo management platform with face recognition (ArcFace 512-d), GPS map view, person clustering, albums, and search. Built with **FastAPI**, **React 18 + Vite**, **PostgreSQL (pgvector)**, and **Redis** — all orchestrated via Docker Compose.

- **Frontend:** http://localhost:5173 (dev), http://localhost:3000 (prod)
- **Backend API:** http://localhost:8000 + Swagger at /docs
- **Status:** Phase 1 complete (core backend + photo serving); Phases 2–3 in progress
- **Default creds:** admin / admin123

---

## Tech Stack & Key Dependencies

### Backend (Python 3.12+)
- **FastAPI** 0.115+ (async web framework)
- **SQLAlchemy** 2.0+ with asyncio & asyncpg
- **PostgreSQL** with **pgvector** (for 512-d face embeddings)
- **Alembic** (database migrations)
- **Celery** + Redis (task queue, session cache)
- **Pillow** + pillow-heif (image ops, HEIF support)
- **DeepFace** (face detection & embedding generation)
- **DBSCAN** (face clustering)
- **exifread** (EXIF metadata parsing)
- **geopy** (reverse geocoding)

### Frontend (Node 18+)
- **React** 18.3 + **TypeScript** 5.7
- **Vite** 6.0 (build tool, dev server with HMR)
- **React Router** v6 (routing)
- **TanStack React Query** 5.62 (server state)
- **Zustand** 5.0 (client state)
- **Axios** (HTTP client)
- **TailwindCSS** 3.4 (styling)
- **react-photo-album** + **yet-another-react-lightbox** (gallery UI)
- **react-leaflet** + Leaflet (maps)
- **date-fns** (date formatting)
- **ESLint** 9.16 (linting)

### Infrastructure
- **Docker Desktop** 24+ with Compose v2
- **PostgreSQL** 15 (primary DB)
- **Redis** 7 (cache + Celery broker)
- **Nginx** (production reverse proxy)

---

## Architecture & Key Directories

```
PhotosApp/
├── backend/                          # FastAPI application
│   ├── app/
│   │   ├── main.py                  # App startup, lifespan events, CORS
│   │   ├── config.py                # Settings (env-based, dataclass)
│   │   ├── api/v1/
│   │   │   ├── router.py            # Route registration (includes all routers)
│   │   │   ├── auth.py              # Auth endpoints (login, refresh)
│   │   │   ├── photos.py            # Photo CRUD, file serving, thumbnails
│   │   │   ├── faces.py             # Face listing, confirmation workflow
│   │   │   ├── people.py            # Person (cluster) management
│   │   │   ├── map.py               # Geo-indexed photo endpoints
│   │   │   ├── albums.py            # Album CRUD
│   │   │   ├── search.py            # Full-text search
│   │   │   ├── tags.py              # Tag management
│   │   │   ├── jobs.py              # Background job status
│   │   │   └── favorites.py         # Like/favorite endpoints
│   │   ├── core/
│   │   │   ├── database.py          # SQLAlchemy engine + session factory
│   │   │   ├── security.py          # JWT token creation/validation
│   │   │   ├── exceptions.py        # Custom HTTPException subclasses
│   │   │   └── redis.py             # Redis connection pool
│   │   ├── models/
│   │   │   ├── base.py              # Base model + audit timestamps
│   │   │   ├── user.py              # User model (auth)
│   │   │   ├── photo.py             # Photo model (w/ EXIF, size, taken_at)
│   │   │   ├── face.py              # Face detection (bounding box, embedding)
│   │   │   ├── person.py            # Clustered person (representative face)
│   │   │   ├── album.py             # Album (user-defined collections)
│   │   │   ├── location.py          # Reverse-geocoded location cache
│   │   │   ├── tag.py               # Tags (searchable metadata)
│   │   │   └── (others...)          # Relationships & validation
│   │   ├── schemas/
│   │   │   ├── auth.py              # LoginRequest, TokenResponse
│   │   │   ├── photo.py             # PhotoResponse + pagination
│   │   │   ├── face.py              # FaceResponse (w/ embedding)
│   │   │   ├── album.py             # AlbumCreate, AlbumUpdate
│   │   │   └── (others...)          # DTO schemas (Pydantic v2)
│   │   ├── services/
│   │   │   ├── scanner.py           # Scan photos dir, index new files, geocode
│   │   │   ├── face_detector.py     # DeepFace.extract_faces() wrapper
│   │   │   ├── face_cluster.py      # DBSCAN clustering on embeddings
│   │   │   ├── thumbnail.py         # Generate + cache thumbnails
│   │   │   ├── exif.py              # Parse EXIF, extract taken_at
│   │   │   ├── geocoder.py          # Reverse-geocode coords to address
│   │   │   └── (others...)          # Business logic layers
│   │   ├── scripts/
│   │   │   ├── seed.py              # Create admin user on startup
│   │   │   ├── scan.py              # Manual photo scan trigger
│   │   │   ├── cluster_faces.py     # Manual face clustering script
│   │   │   └── (others...)          # One-off CLI utilities
│   │   ├── workers/
│   │   │   ├── celery_app.py        # Celery app config
│   │   │   ├── pipeline.py          # Orchestrate multi-step tasks
│   │   │   └── tasks/               # Individual Celery task definitions
│   │   ├── watcher/
│   │   │   └── file_watcher.py      # (Not yet active) File system watcher
│   │   └── utils/
│   │       ├── path.py              # Photo path resolving logic
│   │       └── geo.py               # Geo utility functions
│   ├── alembic/
│   │   ├── versions/                # Migration files (0001_initial_schema.py, etc.)
│   │   └── env.py                   # Alembic runtime config
│   ├── pyproject.toml               # Dependencies, script entry points
│   ├── alembic.ini                  # Alembic CLI config
│   └── Dockerfile                   # Multistage build: deps → app
│
├── frontend/                         # React + Vite application
│   ├── src/
│   │   ├── main.tsx                 # React entry point
│   │   ├── App.tsx                  # Root route wrapper
│   │   ├── index.css                # Global styles + TailwindCSS directives
│   │   ├── api/
│   │   │   ├── client.ts            # Axios instance + interceptors
│   │   │   ├── auth.ts              # /auth endpoints
│   │   │   ├── photos.ts            # /photos endpoints
│   │   │   ├── faces.ts             # /faces endpoints
│   │   │   ├── people.ts            # /people endpoints
│   │   │   ├── map.ts               # /map endpoints
│   │   │   ├── albums.ts            # /albums endpoints
│   │   │   ├── search.ts            # /search endpoints
│   │   │   └── (others...)          # Domain-specific API wrappers
│   │   ├── components/
│   │   │   ├── layout/              # Header, Sidebar, Footer
│   │   │   ├── photos/              # Photo grid, Lightbox, LazyLoad
│   │   │   ├── map/                 # Map view, markers
│   │   │   ├── common/              # Reusable UI (Button, Modal, etc.)
│   │   │   └── (others...)          # Domain components
│   │   ├── pages/
│   │   │   ├── LibraryPage.tsx      # Main library view (tabs: All, Months, Faces, Map, Albums)
│   │   │   ├── AlbumDetailPage.tsx  # Single album view
│   │   │   ├── LoginPage.tsx        # Auth entry point
│   │   │   └── (others...)          # Other top-level pages
│   │   ├── hooks/
│   │   │   ├── usePhotos.ts         # React Query hook for photos list
│   │   │   ├── useAuth.ts           # Auth context + login/logout
│   │   │   ├── useSearch.ts         # Search state + API call
│   │   │   ├── useFaces.ts          # Face listing + clustering state
│   │   │   ├── useMap.ts            # Map view state
│   │   │   └── (others...)          # Custom hooks
│   │   ├── stores/
│   │   │   └── (Zustand stores)     # Global client state (if not using context)
│   │   ├── types/
│   │   │   └── index.ts             # Shared TypeScript types
│   │   ├── utils/
│   │   │   └── (utility functions)  # Helpers, formatters, validators
│   │   └── vite-env.d.ts            # Vite type declarations
│   ├── index.html                   # HTML entry point
│   ├── package.json                 # Dependencies, build scripts
│   ├── tsconfig.json                # TypeScript config
│   ├── vite.config.ts               # Vite build + dev server config
│   ├── tailwind.config.ts           # TailwindCSS theming
│   ├── postcss.config.js            # PostCSS pipeline (TailwindCSS)
│   ├── Dockerfile                   # Multistage: build → serve via Nginx
│   └── eslintrc.js                  # ESLint rules
│
├── nginx/
│   └── default.conf                 # Nginx reverse proxy config (prod only)
│
├── docker-compose.yml               # Production compose (no volumes)
├── docker-compose.dev.yml           # Dev overrides (hot reload volumes)
├── Makefile                         # Common commands (dev, migrate, seed, scan)
├── .env                             # Environment variables (git-ignored)
├── .env.example                     # Template for .env
├── README.md                        # Quick start guide
└── docs/
    ├── ARCHITECTURE.md              # System design, data flow
    ├── DATABASE_SCHEMA.md           # Tables, relationships, indexes
    ├── API_ENDPOINTS.md             # Route documentation
    └── PROJECT_STRUCTURE.md         # Directory overview
```

---

## Development Workflow

### Prerequisites
- **Docker Desktop** 24+ (includes Compose v2) — [Download](https://www.docker.com/products/docker-desktop/)
- **Git** (any recent version)
- **macOS/Linux/Windows** with WSL2 for Windows

### Initial Setup

```bash
# 1. Clone repo
git clone https://github.com/skckadiyala/PhotosApp.git
cd PhotosApp

# 2. Copy .env template and customize HOST_PHOTOS_DIR
cp .env.example .env
# Edit .env with your photo directory path (macOS: /Volumes/..., Linux: /mnt/..., or ./test_photos)

# 3. Start all services in dev mode (hot reload enabled)
make dev
# On first run, this downloads base images and installs dependencies (~5–10 min)

# 4. In a new terminal, run migrations + seed admin
make migrate
make seed

# 5. Open http://localhost:5173 (frontend) or http://localhost:8000/docs (API docs)
# Login: admin / admin123
```

### Common Development Commands

```bash
# See all available commands
make help

# Start dev environment (hot reload for both backend & frontend)
make dev

# View live logs from all containers
make logs

# Run database migrations
make migrate

# Seed initial admin user
make seed

# Trigger full photo library scan + geocoding
make scan

# Run face detection on unprocessed photos
make detect-faces

# Run DBSCAN clustering on face embeddings
make cluster-faces

# Open bash shell in backend container
make shell-backend

# Open psql shell to query database directly
make shell-db

# Build production images
make build

# Start in production mode (Nginx serves frontend)
make up

# Stop all services
make down

# **DESTRUCTIVE:** Remove containers, volumes, and images (clears DB!)
make clean
```

### Hot Reload Setup

**Backend (Python):**
- `docker-compose.dev.yml` mounts `/backend` source code into the container
- Uvicorn runs with `--reload` flag (watches for file changes)
- Restart happens automatically on code save

**Frontend (React):**
- `docker-compose.dev.yml` mounts `/frontend/src` into Vite dev server
- Vite HMR (Hot Module Replacement) updates browser on save
- No full page reload needed for most changes

### Editor Integration

**VS Code:**
- Install **Python** (Microsoft) + **Pylance** (type checking for backend)
- Install **TypeScript Vue Plugin (Volar)** for React/TS in frontend
- ESLint runs on save via `make lint` (run manually or via editor plugin)

---

## Code Conventions & Patterns

### Backend (FastAPI + SQLAlchemy)

#### Route Structure
- All routes are in `backend/app/api/v1/{domain}.py` (e.g., `photos.py`, `faces.py`)
- Routes are registered in `router.py` via `api_router.include_router()`
- Prefix: `/api/v1/{domain}` (e.g., `/api/v1/photos`, `/api/v1/faces`)

#### Example Route Pattern
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.models import Photo, User
from app.schemas.photo import PhotoResponse, PhotoListResponse

router = APIRouter()

@router.get("", response_model=PhotoListResponse)
async def list_photos(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return paginated photos for the current user."""
    photos = await db.execute(
        select(Photo)
        .where(Photo.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    return {"items": photos.scalars().all(), "total": len(photos.all())}
```

#### Auth Pattern
- JWT token-based (HS256 algorithm)
- `Depends(get_current_user)` enforces auth on protected routes
- Tokens stored in HTTPOnly cookies (frontend autoconfigures via Axios interceptor)
- Refresh token endpoint at `POST /api/v1/auth/refresh`

#### Database Pattern
- Use `AsyncSession` in routes (async/await throughout)
- Always filter by `current_user.id` to enforce multi-user isolation
- Use `select(Model).where(...)` pattern (SQLAlchemy 2.0 ORM style)
- Lazy-load relationships carefully (avoid N+1 queries)

#### Error Handling
- Raise `HTTPException(status_code=404, detail="Photo not found")`
- Catch and wrap service exceptions with meaningful errors
- Avoid exposing internal stack traces in production

### Frontend (React + TypeScript)

#### Component Structure
```tsx
export interface MyComponentProps {
  photoId: string;
  onSelect?: (id: string) => void;
}

export function MyComponent({ photoId, onSelect }: MyComponentProps) {
  const [state, setState] = useState<string | null>(null);
  
  const handleClick = () => {
    onSelect?.(photoId);
  };

  return <div onClick={handleClick}>{/* UI */}</div>;
}
```

#### Hook Pattern
```tsx
export function usePhotos(skip: number = 0, limit: number = 50) {
  return useQuery({
    queryKey: ["photos", skip, limit],
    queryFn: () => api.photos.getList({ skip, limit }),
    staleTime: 60 * 1000, // 1 minute
  });
}
```

#### Zustand State (if used)
```tsx
interface PhotoStore {
  selected: string[];
  addToSelection: (id: string) => void;
  clear: () => void;
}

export const usePhotoStore = create<PhotoStore>((set) => ({
  selected: [],
  addToSelection: (id: string) =>
    set((state) => ({ selected: [...state.selected, id] })),
  clear: () => set({ selected: [] }),
}));
```

#### Routing Pattern
```tsx
// In App.tsx or a router config file
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LibraryPage } from "./pages/LibraryPage";

<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route
    path="/library"
    element={<ProtectedRoute><LibraryPage /></ProtectedRoute>}
  />
</Routes>
```

#### API Client Pattern
```tsx
// src/api/photos.ts
import { client } from "./client";

export const photos = {
  async getList(params: { skip?: number; limit?: number }) {
    const response = await client.get("/photos", { params });
    return response.data; // PhotoListResponse
  },
  async getById(id: string) {
    const response = await client.get(`/photos/${id}`);
    return response.data; // PhotoResponse
  },
};
```

#### Lazy Loading & Virtualization
- Use **react-intersection-observer** for viewport detection
- Render images only when they enter the viewport
- Use memo() to prevent unnecessary re-renders of grid items
- Combine with React Query for efficient fetching

---

## Testing & Build

### Backend Testing
```bash
# Run inside backend container
make shell-backend

# Run pytest (if tests exist)
pytest tests/ -v

# Type check with Pylance / mypy
mypy app/
```

### Frontend Linting & Build
```bash
# Lint
npm run lint

# Build (type-check + vite build)
npm run build

# Preview production build locally
npm run preview
```

### Database Migrations
```bash
# Create migration after schema changes
make shell-backend
alembic revision --autogenerate -m "Add new column to photos"

# Verify migration
alembic current
alembic history --verbose

# Upgrade to latest
make migrate

# Downgrade one step
alembic downgrade -1
```

---

## Debugging Tips

### Backend Debugging

1. **View Logs**
   ```bash
   make logs | grep backend
   ```

2. **Inspect Database**
   ```bash
   make shell-db
   # Then: SELECT * FROM photo LIMIT 10;
   ```

3. **Call API Directly**
   ```bash
   curl -X GET http://localhost:8000/api/v1/photos \
     -H "Authorization: Bearer YOUR_JWT_TOKEN"
   ```

4. **Swagger Docs**
   - Open http://localhost:8000/docs
   - Authenticate at the top
   - Try endpoints directly

5. **Add Logging**
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info("Custom debug message: %s", variable)
   ```

### Frontend Debugging

1. **React DevTools**
   - Install [React Developer Tools](https://chrome.google.com/webstore/detail/) Chrome extension
   - Inspect component props, state, and hooks

2. **Network Tab**
   - Open DevTools → Network
   - Check XHR/Fetch requests to `/api/v1/*`
   - Verify JWT token in request headers

3. **Console Errors**
   - Look for TypeScript compilation errors
   - Check Axios interceptor logic
   - Verify API response shape matches TypeScript types

4. **Vite Dev Server**
   - HMR should auto-update on save
   - If stuck, restart: `make dev`

---

## Common Issues & Gotchas

### Issue: Photos Not Appearing After Upload
- **Root cause:** Scanner runs async in background; may not have finished yet
- **Fix:** Click the manual scan button in UI or run `make scan`
- **Prevention:** Monitor logs (`make logs`) for scanner progress

### Issue: Face Detection Very Slow
- **Root cause:** DeepFace is CPU-intensive; GPU acceleration not enabled by default
- **Fix:** Use smaller batch size in `face_detector.py` or run overnight
- **Prevention:** Cluster incrementally; don't process entire library at once

### Issue: Database Migration Conflicts
- **Root cause:** Multiple migration files with same timestamp
- **Fix:** Manually edit migration names to avoid collisions
- **Prevention:** Pull latest `alembic/versions/` before creating new migrations

### Issue: JWT Token Expired (401 Errors)
- **Root cause:** Access token expires after 15 minutes by default
- **Fix:** Frontend auto-refreshes via refresh token endpoint
- **Prevention:** Check `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env` (should be ≥ 15)

### Issue: Frontend Won't Connect to Backend (CORS Error)
- **Root cause:** CORS middleware not configured or origin mismatch
- **Fix:** In `main.py`, ensure `allow_origins` includes `localhost:5173` (dev)
- **Prevention:** Check `backend/app/main.py` for CORSMiddleware setup

### Issue: Docker Container Won't Start
- **Root cause:** Port conflict (5173, 8000, 5432 already in use)
- **Fix:** Run `docker ps` to find conflicting containers; stop them or change ports in `.env`
- **Prevention:** Don't run multiple instances of PhotosApp simultaneously

### Issue: Thumbnail Cache Not Updating
- **Root cause:** Thumbnails are cached; old images still served
- **Fix:** Delete thumbnail cache: `docker compose exec backend rm -rf /data/thumbnails`
- **Prevention:** Implement cache invalidation on photo deletion

---

## Performance Considerations

### Database
- Face embeddings (512-d pgvector) are indexed; queries are fast
- Pagination (skip/limit) is **required** for large libraries (100K+ photos)
- Pre-fetch relationships in service layers to avoid N+1

### Frontend
- Use React.memo() on photo grid items
- Virtualize long lists with react-window or similar
- Lazy-load images with react-intersection-observer
- Compress/resize thumbnails in backend before serving

### Image Processing
- Thumbnails are generated once and cached
- Face detection is offloaded to Celery workers (non-blocking)
- Geocoding batches requests to avoid rate limits
- Clustering happens async; manual trigger recommended for large libraries

---

## Deployment & Production

### Environment Variables
Set these before `make build` and `make up`:
- `SECRET_KEY` – Generate a strong random string
- `POSTGRES_PASSWORD` – Use a real password (not dev default)
- `ADMIN_PASSWORD` – Strong password for admin account
- `HOST_PHOTOS_DIR` – Path to actual photo library on host
- (Optionally) `ACCESS_TOKEN_EXPIRE_MINUTES`, `REDIS_HOST`, etc.

### Build for Production
```bash
make build
make up  # Starts Nginx on :3000
```

### Monitoring
- Logs: `docker compose logs -f`
- Database size: `make shell-db` → `\l` (list databases)
- Redis: Install redis-cli locally; `redis-cli -h localhost COMMAND`

---

## Related Documentation

- [ARCHITECTURE.md](../docs/ARCHITECTURE.md) – System design, data flow, async tasks
- [DATABASE_SCHEMA.md](../docs/DATABASE_SCHEMA.md) – Tables, indexes, relationships
- [API_ENDPOINTS.md](../docs/API_ENDPOINTS.md) – Route documentation + examples
- [PROJECT_STRUCTURE.md](../docs/PROJECT_STRUCTURE.md) – Directory tree explanation

---

## Tips for AI Agents

1. **Always check `.env` first** – understand HOST_PHOTOS_DIR, database credentials, feature flags
2. **Use `make help`** when unsure of next step
3. **Read error messages carefully** – they often point to the root cause (DB migration, JWT expiry, CORS, port conflict)
4. **Inspect existing patterns** – look at similar routes/components before creating new ones
5. **Test changes incrementally** – `make dev`, then validate in browser or via `curl` to `/docs`
6. **Run migrations before seeding** – migrations must succeed first, then seed can create admin
7. **Keep async/await consistent** – backend uses async SQLAlchemy; don't mix sync calls
8. **Frontend: Always pass `userId` filter** – ensure multi-user isolation on backend routes
9. **Check React Query cache keys** – mismatches cause stale data; use predictable key naming
10. **Document decisions** – if you make architectural changes, update `docs/` files

---

**Last updated:** 2026-03-19  
**Maintained by:** PhotosApp team
