"""Owner-only complete-layout saves and explicit activation."""

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.api.dependencies import Database, Owner
from app.models import Mosaic
from app.repositories import mosaics, profiles
from app.schemas.mosaic import MosaicCreate, MosaicLayout, MosaicRead, Preset
from app.services.mosaic import PRESETS, expand_preset, uses_featured_albums

router = APIRouter(prefix="/api/me", tags=["mosaics"])


def read_mosaic(mosaic: Mosaic) -> MosaicRead:
    return MosaicRead(
        id=mosaic.id,
        is_active=mosaic.is_active,
        preset_key=mosaic.preset_key,
        grid_width=mosaic.grid_width,
        grid_height=mosaic.grid_height,
        tiles=mosaic.tiles,
    )


@router.get("/mosaic-presets", response_model=list[Preset])
async def get_presets(profile: Owner):
    return PRESETS


@router.get("/mosaics", response_model=list[MosaicRead])
async def get_mosaics(db: Database, profile: Owner):
    async with db.begin():
        mosaic = await mosaics.get_by_profile_id(db, profile.id)
        return [read_mosaic(mosaic)] if mosaic else []


@router.post("/mosaics", response_model=MosaicRead, status_code=201)
async def create_mosaic(body: MosaicCreate, db: Database, profile: Owner):
    async with db.begin():
        # Lock the profile so concurrent creates/selection changes serialize.
        profile = await profiles.get_for_update(db, profile.user_id)
        if await mosaics.get_by_profile_id(db, profile.id):
            raise HTTPException(409, "A mosaic already exists for this profile")
        mosaic = await mosaics.create(
            db,
            profile.id,
            expand_preset(body.preset_key, profile.featured_album_ids),
        )
        return read_mosaic(mosaic)


@router.put("/mosaics/{mosaic_id}", response_model=MosaicRead)
async def save_mosaic(
    mosaic_id: UUID, body: MosaicLayout, db: Database, profile: Owner
):
    async with db.begin():
        profile = await profiles.get_for_update(db, profile.user_id)
        mosaic = await mosaics.get_for_update(db, profile.id)
        if mosaic is None or mosaic.id != mosaic_id:
            raise HTTPException(404, "Mosaic not found")
        if not uses_featured_albums(body, profile.featured_album_ids):
            raise HTTPException(422, "mosaic_album_not_featured")
        await mosaics.save(db, mosaic, body)
        return read_mosaic(mosaic)


@router.post("/mosaics/{mosaic_id}/activate", response_model=MosaicRead)
async def activate_mosaic(mosaic_id: UUID, db: Database, profile: Owner):
    async with db.begin():
        mosaic = await mosaics.get_for_update(db, profile.id)
        if mosaic is None or mosaic.id != mosaic_id:
            raise HTTPException(404, "Mosaic not found")
        await mosaics.activate(db, mosaic)
        return read_mosaic(mosaic)
