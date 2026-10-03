from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import (
    auth_router,
    me_router,
    spotify_router,
)


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
)


app.include_router(spotify_router)
app.include_router(auth_router)
app.include_router(me_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}