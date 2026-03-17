# PhotosApp — Database Schema

## Entity Relationship Diagram

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│    users     │       │    photos    │       │   locations  │
├──────────────┤       ├──────────────┤       ├──────────────┤
│ id (PK)      │──┐    │ id (PK)      │──────►│ id (PK)      │
│ username     │  │    │ file_path    │       │ latitude     │
│ email        │  │    │ file_name    │       │ longitude    │
│ password_hash│  │    │ file_hash    │       │ altitude     │
│ role         │  │    │ file_size    │       │ city         │
│ created_at   │  │    │ mime_type    │       │ state        │
│ updated_at   │  │    │ width        │       │ country      │
└──────────────┘  │    │ height       │       │ formatted    │
                  │    │ taken_at     │       │ created_at   │
                  │    │ camera_make  │       └──────────────┘
                  │    │ camera_model │
                  │    │ lens_model   │       ┌──────────────┐
                  │    │ f_number     │       │   people     │
                  │    │ exposure_time│       ├──────────────┤
                  │    │ iso          │  ┌───►│ id (PK)      │
                  │    │ focal_length │  │    │ name         │
                  │    │ orientation  │  │    │ cover_face_id│
                  │    │ location_id  │──┘    │ photo_count  │
                  │    │ is_favorite  │  │    │ created_at   │
                  │    │ is_hidden    │  │    │ updated_at   │
                  │    │ is_processed │  │    └──────┬───────┘
                  │    │ thumb_sm     │  │           │
                  │    │ thumb_md     │  │           │
                  │    │ thumb_lg     │  │    ┌──────┴───────┐
                  └───►│ user_id (FK) │  │    │    faces     │
                       │ created_at   │  │    ├──────────────┤
                       │ updated_at   │  │    │ id (PK)      │
                       └──────┬───────┘  │    │ photo_id (FK)│───► photos
                              │          │    │ person_id(FK)│───► people
                              │          │    │ bbox_x       │
                              │          │    │ bbox_y       │
                              │          │    │ bbox_w       │
                              │          │    │ bbox_h       │
                              │          │    │ embedding    │ (vector(512))
                              │          │    │ confidence   │
                              │          │    │ cluster_id   │
                              │          │    │ created_at   │
                              │          │    └──────────────┘
                              │
                    ┌─────────┴──────────┐
                    │                    │
             ┌──────┴───────┐    ┌──────┴───────┐
             │  photo_tags  │    │ album_photos │
             ├──────────────┤    ├──────────────┤
             │ photo_id(FK) │    │ album_id(FK) │───► albums
             │ tag_id (FK)  │    │ photo_id(FK) │───► photos
             │ confidence   │    │ sort_order   │
             │ source       │    │ added_at     │
             └──────┬───────┘    └──────┬───────┘
                    │                    │
             ┌──────┴───────┐    ┌──────┴───────┐
             │    tags      │    │   albums     │
             ├──────────────┤    ├──────────────┤
             │ id (PK)      │    │ id (PK)      │
             │ name         │    │ name         │
             │ category     │    │ description  │
             │ created_at   │    │ cover_photo_id│
             └──────────────┘    │ user_id (FK) │
                                 │ is_smart     │
                                 │ smart_rules  │ (JSONB)
                                 │ photo_count  │
                                 │ created_at   │
                                 │ updated_at   │
                                 └──────────────┘
```

---

## Table Definitions (SQL)

### users
```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(50) UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'user',  -- 'admin' | 'user' | 'viewer'
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
```

### photos
```sql
CREATE TABLE photos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path       TEXT UNIQUE NOT NULL,           -- Relative to mount root: "2024/vacation/IMG_001.jpg"
    file_name       VARCHAR(255) NOT NULL,
    file_hash       VARCHAR(64) NOT NULL,           -- SHA-256 for dedup
    file_size       BIGINT NOT NULL,                -- Bytes
    mime_type       VARCHAR(50) NOT NULL,            -- "image/jpeg", "image/png", etc.
    width           INTEGER,
    height          INTEGER,

    -- EXIF metadata
    taken_at        TIMESTAMPTZ,                    -- Date photo was taken
    camera_make     VARCHAR(100),
    camera_model    VARCHAR(100),
    lens_model      VARCHAR(100),
    f_number        REAL,
    exposure_time   VARCHAR(20),                    -- "1/250"
    iso             INTEGER,
    focal_length    REAL,
    orientation     SMALLINT,                       -- EXIF orientation (1-8)

    -- Relations
    location_id     UUID REFERENCES locations(id) ON DELETE SET NULL,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Flags
    is_favorite     BOOLEAN NOT NULL DEFAULT FALSE,
    is_hidden       BOOLEAN NOT NULL DEFAULT FALSE,
    is_processed    BOOLEAN NOT NULL DEFAULT FALSE,  -- All background tasks done

    -- Thumbnails (relative paths in cache dir)
    thumb_sm        VARCHAR(500),                    -- 200px
    thumb_md        VARCHAR(500),                    -- 800px
    thumb_lg        VARCHAR(500),                    -- 1920px

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_photos_taken_at ON photos(taken_at DESC);
CREATE INDEX idx_photos_file_hash ON photos(file_hash);
CREATE INDEX idx_photos_user ON photos(user_id);
CREATE INDEX idx_photos_location ON photos(location_id);
CREATE INDEX idx_photos_favorite ON photos(user_id, is_favorite) WHERE is_favorite = TRUE;
CREATE INDEX idx_photos_not_processed ON photos(is_processed) WHERE is_processed = FALSE;
```

### locations
```sql
CREATE TABLE locations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    latitude    DOUBLE PRECISION NOT NULL,
    longitude   DOUBLE PRECISION NOT NULL,
    altitude    REAL,
    city        VARCHAR(200),
    state       VARCHAR(200),
    country     VARCHAR(100),
    formatted   TEXT,                               -- Full formatted address
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_locations_coords ON locations(latitude, longitude);
CREATE INDEX idx_locations_city ON locations(city);
CREATE INDEX idx_locations_country ON locations(country);
```

### people
```sql
CREATE TABLE people (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200),                   -- NULL = unnamed cluster
    cover_face_id   UUID,                           -- Best face thumbnail (FK set after faces table)
    photo_count     INTEGER NOT NULL DEFAULT 0,     -- Denormalized count
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_people_name ON people(name);
```

### faces
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE faces (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id    UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    person_id   UUID REFERENCES people(id) ON DELETE SET NULL,

    -- Bounding box (pixel coordinates in original image)
    bbox_x      INTEGER NOT NULL,
    bbox_y      INTEGER NOT NULL,
    bbox_w      INTEGER NOT NULL,
    bbox_h      INTEGER NOT NULL,

    -- Face embedding vector for similarity search
    embedding   vector(512) NOT NULL,               -- 512-dim for InsightFace (128 for dlib)

    confidence  REAL NOT NULL DEFAULT 0.0,          -- Detection confidence 0-1
    cluster_id  INTEGER,                            -- DBSCAN cluster assignment

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_faces_photo ON faces(photo_id);
CREATE INDEX idx_faces_person ON faces(person_id);
CREATE INDEX idx_faces_cluster ON faces(cluster_id);

-- HNSW index for fast approximate nearest neighbor on embeddings
CREATE INDEX idx_faces_embedding ON faces
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Add FK from people.cover_face_id → faces.id
ALTER TABLE people
    ADD CONSTRAINT fk_people_cover_face
    FOREIGN KEY (cover_face_id) REFERENCES faces(id) ON DELETE SET NULL;
```

### tags
```sql
CREATE TABLE tags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) UNIQUE NOT NULL,
    category    VARCHAR(50),                        -- 'object', 'scene', 'color', 'custom'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_tags_category ON tags(category);
```

### photo_tags (junction table)
```sql
CREATE TABLE photo_tags (
    photo_id    UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    tag_id      UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    confidence  REAL DEFAULT 1.0,                   -- AI confidence (1.0 for manual tags)
    source      VARCHAR(20) NOT NULL DEFAULT 'ai',  -- 'ai' | 'manual'
    PRIMARY KEY (photo_id, tag_id)
);

CREATE INDEX idx_photo_tags_tag ON photo_tags(tag_id);
```

### albums
```sql
CREATE TABLE albums (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    cover_photo_id  UUID REFERENCES photos(id) ON DELETE SET NULL,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Smart album support
    is_smart        BOOLEAN NOT NULL DEFAULT FALSE,
    smart_rules     JSONB,                          -- e.g. {"tags": ["beach"], "date_range": ["2024-01-01", "2024-12-31"]}

    photo_count     INTEGER NOT NULL DEFAULT 0,     -- Denormalized
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_albums_user ON albums(user_id);
```

### album_photos (junction table)
```sql
CREATE TABLE album_photos (
    album_id    UUID NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
    photo_id    UUID NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (album_id, photo_id)
);

CREATE INDEX idx_album_photos_album ON album_photos(album_id);
```

---

## Smart Album Rules (JSONB Schema)

```jsonc
{
    // All conditions are AND-ed together
    "tags": ["beach", "sunset"],           // Must have ALL these tags
    "tags_any": ["vacation", "travel"],    // Must have ANY of these tags
    "people": ["uuid-1", "uuid-2"],        // Must contain face of these people
    "date_range": ["2024-01-01", "2024-12-31"],
    "locations": ["Paris", "London"],       // City name match
    "camera_model": "iPhone 15 Pro",
    "is_favorite": true,
    "min_rating": 4
}
```

---

## Migration Strategy

Using **Alembic** for schema migrations:

```bash
# Generate a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```
