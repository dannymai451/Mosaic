from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.albums import router as albums_router
from app.api.routes.auth import (
    auth_router,
    me_router,
    spotify_router,
)
from app.api.routes.mosaics import router as mosaics_router
from app.api.routes.profiles import public_router
from app.api.routes.profiles import router as profiles_router

app = FastAPI(
    title="Mosaic API",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


app.include_router(spotify_router)
app.include_router(auth_router)
app.include_router(me_router)
app.include_router(profiles_router)
app.include_router(public_router)
app.include_router(albums_router)
app.include_router(mosaics_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
