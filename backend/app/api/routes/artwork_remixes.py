"""Owner remix studio and opt-in, narrowly scoped public artwork links."""

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import Database, Owner, spotify_for_owner
from app.models import MonthlyMosaic, Profile
from app.repositories import artwork_remixes as remixes
from app.repositories import monthly_mosaics, profiles, spotify_connections
from app.schemas.artwork_remix import RemixWrite
from app.schemas.monthly_mosaic import MonthlyAlbum
from app.services import spotify_cache
from app.services.artwork_remix import normalize_background, remix_layout, shape_catalog
from app.services.spotify import TOP_SCOPE

router = APIRouter(tags=["artwork-remixes"])
AlbumPath = Annotated[str, Path(pattern=r"^[a-zA-Z0-9]{22}$")]
TrackQuery = Annotated[str | None, Query(pattern=r"^[a-zA-Z0-9]{22}$")]
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


def missing():
    return HTTPException(404, "Artwork not found", headers=NO_STORE)


def read_remix(remix, snapshot, *, public=False, display_name=None):
    root = (
        f"/api/artworks/{remix.share_id}" if public else f"/api/me/remixes/{remix.id}"
    )
    result = {
        "name": remix.name,
        "month": snapshot.month.strftime("%Y-%m"),
        "style": remix.style,
        "layout": remix.layout,
        "background_url": f"{root}/background?v={remix.background_version}"
        if remix.has_background
        else None,
    }
    if public:
        result["display_name"] = display_name
    else:
        result.update(id=remix.id, share_id=remix.share_id)
    return result


async def owned(db, profile, remix_id):
    remix = await remixes.get_owned(db, profile.id, remix_id)
    if remix is None:
        raise missing()
    return remix


async def shared(db, share_id):
    remix = await remixes.get_shared(db, share_id)
    if remix is None:
        raise missing()
    snapshot = await db.get(MonthlyMosaic, remix.monthly_mosaic_id)
    profile = await db.get(Profile, snapshot.profile_id)
    return remix, snapshot, profile


@router.get("/api/me/remix-shapes")
async def get_shapes(profile: Owner):
    return {"items": shape_catalog()}


@router.get("/api/me/monthly-mosaics/{mosaic_id}/remixes")
async def list_remixes(mosaic_id: UUID, db: Database, profile: Owner):
    async with db.begin():
        snapshot = await monthly_mosaics.get_owned(db, profile.id, mosaic_id)
        if snapshot is None:
            raise missing()
        return {
            "items": [
                read_remix(item, snapshot)
                for item in await remixes.list_for_month(db, mosaic_id)
            ]
        }


@router.post("/api/me/monthly-mosaics/{mosaic_id}/remixes", status_code=201)
async def create_remix(mosaic_id: UUID, body: RemixWrite, db: Database, profile: Owner):
    async with db.begin():
        await profiles.get_for_update(db, profile.user_id)
        snapshot = await monthly_mosaics.get_owned(db, profile.id, mosaic_id)
        if snapshot is None:
            raise missing()
        if len(await remixes.list_for_month(db, mosaic_id)) >= 12:
            raise HTTPException(409, "You can save up to 12 remixes for this month")
        remix = await remixes.create(
            db,
            mosaic_id,
            name=body.name.strip() or "Untitled remix",
            style=body.style.model_dump(),
            layout=remix_layout(snapshot, body.style.shape),
        )
        return read_remix(remix, snapshot)


@router.put("/api/me/remixes/{remix_id}")
async def update_remix(remix_id: UUID, body: RemixWrite, db: Database, profile: Owner):
    async with db.begin():
        await profiles.get_for_update(db, profile.user_id)
        remix = await owned(db, profile, remix_id)
        snapshot = await db.get(MonthlyMosaic, remix.monthly_mosaic_id)
        await remixes.update(
            db,
            remix,
            name=body.name.strip() or "Untitled remix",
            style=body.style.model_dump(),
            layout=remix_layout(snapshot, body.style.shape),
        )
        return read_remix(remix, snapshot)


@router.delete("/api/me/remixes/{remix_id}", status_code=204)
async def delete_remix(remix_id: UUID, db: Database, profile: Owner):
    async with db.begin():
        await profiles.get_for_update(db, profile.user_id)
        await remixes.delete(db, await owned(db, profile, remix_id))


@router.put("/api/me/remixes/{remix_id}/background")
async def upload_background(
    remix_id: UUID, request: Request, db: Database, profile: Owner
):
    async with db.begin():
        await owned(db, profile, remix_id)
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 8_000_000:
            raise HTTPException(413, "Choose an image under 8 MB")
    try:
        photo = await run_in_threadpool(normalize_background, bytes(content))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    async with db.begin():
        await profiles.get_for_update(db, profile.user_id)
        remix = await owned(db, profile, remix_id)
        await remixes.update(
            db,
            remix,
            background_image=photo,
            has_background=True,
            background_version=remix.background_version + 1,
        )
        return read_remix(remix, await db.get(MonthlyMosaic, remix.monthly_mosaic_id))


@router.delete("/api/me/remixes/{remix_id}/background")
async def remove_background(remix_id: UUID, db: Database, profile: Owner):
    async with db.begin():
        await profiles.get_for_update(db, profile.user_id)
        remix = await owned(db, profile, remix_id)
        await remixes.update(
            db,
            remix,
            background_image=None,
            has_background=False,
            background_version=remix.background_version + 1,
        )
        return read_remix(remix, await db.get(MonthlyMosaic, remix.monthly_mosaic_id))


@router.get("/api/me/remixes/{remix_id}/background")
async def owner_background(remix_id: UUID, db: Database, profile: Owner):
    async with db.begin():
        remix = await owned(db, profile, remix_id)
        image = await remixes.background(db, remix.id)
        if not image:
            raise missing()
        return Response(image, media_type="image/jpeg", headers=NO_STORE)


@router.post("/api/me/remixes/{remix_id}/share")
async def enable_share(remix_id: UUID, db: Database, profile: Owner):
    async with db.begin():
        await profiles.get_for_update(db, profile.user_id)
        remix = await owned(db, profile, remix_id)
        if remix.share_id is None:
            await remixes.update(db, remix, share_id=uuid4())
        return {"share_id": remix.share_id}


@router.delete("/api/me/remixes/{remix_id}/share", status_code=204)
async def disable_share(remix_id: UUID, db: Database, profile: Owner):
    async with db.begin():
        await profiles.get_for_update(db, profile.user_id)
        await remixes.update(db, await owned(db, profile, remix_id), share_id=None)


@router.get("/api/artworks/{share_id}")
async def get_shared_artwork(share_id: UUID, db: Database, response: Response):
    response.headers.update(NO_STORE)
    async with db.begin():
        remix, snapshot, profile = await shared(db, share_id)
        return read_remix(
            remix, snapshot, public=True, display_name=profile.display_name
        )


@router.get("/api/artworks/{share_id}/background")
async def shared_background(share_id: UUID, db: Database):
    async with db.begin():
        remix, _, _ = await shared(db, share_id)
        image = await remixes.background(db, remix.id)
        if not image:
            raise missing()
        return Response(image, media_type="image/jpeg", headers=NO_STORE)


@router.get("/api/artworks/{share_id}/albums/{album_id}", response_model=MonthlyAlbum)
async def shared_album(
    share_id: UUID,
    album_id: AlbumPath,
    db: Database,
    response: Response,
    track_id: TrackQuery = None,
):
    response.headers.update(NO_STORE)
    async with db.begin():
        remix, _, profile = await shared(db, share_id)
        if not any(
            tile["spotifyAlbumId"] == album_id
            and tile.get("spotifyTrackId") == track_id
            for tile in remix.layout["tiles"]
        ):
            raise missing()
        connection = await spotify_connections.get_by_user_id(db, profile.user_id)
        if connection is not None and TOP_SCOPE in connection.scopes.split():
            cached = spotify_cache.monthly_metadata.get(
                (spotify_cache.connection_key(connection), album_id, track_id)
            )
            if cached is not None:
                return cached.model_copy(deep=True)
    async with spotify_for_owner(db, profile, TOP_SCOPE) as spotify:
        return await spotify.monthly_album(album_id, track_id)
