# PhotosApp

A self-hosted photo management application with face recognition, GPS map view, albums, and search. Built with FastAPI, React, PostgreSQL (pgvector), and Redis — all running in Docker.

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | 24+ |
| [Docker Compose](https://docs.docker.com/compose/) | v2 (included with Docker Desktop) |
| Git | any recent version |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/skckadiyala/PhotosApp.git
cd PhotosApp
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Open `.env` and set the path to your photo library on the host machine:

```dotenv
# macOS example
HOST_PHOTOS_DIR=/Volumes/MyDrive/Photos

# Linux example
HOST_PHOTOS_DIR=/mnt/photos

# Relative path (uses the bundled test_photos folder)
HOST_PHOTOS_DIR=./test_photos
```

You can leave all other values as-is for local development.

### 3. Start in development mode (hot reload)

```bash
make dev
```

This builds the images and starts all services with live code reloading. On first run it may take a few minutes to download base images and install dependencies.

### 4. Run database migrations and seed the admin user

Open a second terminal and run:

```bash
make migrate
make seed
```

### 5. Open the app

| URL | Description |
|---|---|
| http://localhost:5173 | Frontend (Vite dev server) |
| http://localhost:8000 | Backend API |
| http://localhost:8000/docs | Interactive API docs (Swagger UI) |

**Default login credentials:**

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin123` |

---

## Production Mode

```bash
make up
```

Frontend is served by Nginx on **http://localhost:3000**.  
No source code is mounted — rebuild images after code changes:

```bash
make build
make up
```

---

## Available Commands

Run `make help` to see all commands:

```
make dev            Start in development mode with hot reload
make up             Start all services in production mode
make down           Stop all services
make logs           Tail logs from all services
make build          Build all Docker images
make migrate        Run database migrations
make seed           Create initial admin user
make scan           Trigger a full photo library scan
make detect-faces   Run face detection on all unprocessed photos
make cluster-faces  Run face clustering (groups faces into people)
make shell-backend  Open a shell inside the backend container
make shell-db       Open a psql shell
make clean          Remove all containers, volumes, and images (destructive)
```

---

## First-Time Photo Setup

After the app is running, index your photos:

```bash
# 1. Scan the photo directory and add photos to the database
make scan

# 2. Detect faces in all photos
make detect-faces

# 3. Cluster detected faces into people groups
make cluster-faces
```

Photos with GPS data will automatically appear on the Map page.

---

## Project Structure

```
PhotosApp/
├── backend/            FastAPI backend (Python)
│   ├── app/
│   │   ├── api/        REST API endpoints
│   │   ├── models/     SQLAlchemy ORM models
│   │   ├── services/   Face detection, scanning, geocoding
│   │   └── workers/    Celery background tasks
│   └── alembic/        Database migrations
├── frontend/           React + TypeScript frontend (Vite)
│   └── src/
│       ├── pages/      Page components
│       ├── components/ Reusable UI components
│       ├── api/        API client functions
│       └── hooks/      React Query hooks
├── nginx/              Nginx config (production)
├── docker-compose.yml          Production compose file
├── docker-compose.dev.yml      Development overrides
└── .env.example                Environment variable template
```

---

## Troubleshooting

**App is spinning / not loading**
```bash
docker restart photosapp-backend-1 photosapp-frontend-1
```

**Backend keeps reloading in a loop**  
The uvicorn `--reload` watcher can trigger on git operations. Restart the backend:
```bash
docker restart photosapp-backend-1
```

**Port already in use**
```bash
make down
make dev
```

**Reset everything (deletes all data)**
```bash
make clean
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `photosapp` | Database username |
| `POSTGRES_PASSWORD` | — | Database password |
| `POSTGRES_DB` | `photosapp` | Database name |
| `SECRET_KEY` | — | JWT signing secret — **change in production** |
| `HOST_PHOTOS_DIR` | `./test_photos` | Path to photo library on the host |
| `PHOTOS_DIR` | `/mnt/photos` | Path inside the container (do not change) |
| `THUMBNAILS_DIR` | `/data/thumbnails` | Thumbnail cache path inside container |
| `ADMIN_USERNAME` | `admin` | Initial admin username |
| `ADMIN_EMAIL` | `admin@photosapp.dev` | Initial admin email |
| `ADMIN_PASSWORD` | `admin123` | Initial admin password — **change in production** |
