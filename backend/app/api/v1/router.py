from fastapi import APIRouter

from app.api.v1 import auth, photos, faces, people, map as map_routes, albums, favorites, search, tags, jobs

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(photos.router, prefix="/photos", tags=["Photos"])
api_router.include_router(faces.router, prefix="/faces", tags=["Faces"])
api_router.include_router(people.router, prefix="/people", tags=["People"])
api_router.include_router(map_routes.router, prefix="/map", tags=["Map"])
api_router.include_router(albums.router, prefix="/albums", tags=["Albums"])
api_router.include_router(favorites.router, prefix="/favorites", tags=["Favorites"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(tags.router, prefix="/tags", tags=["Tags"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
