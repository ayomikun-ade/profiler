from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_http_client
from app.errors import error_response
from app.models import Profile
from app.schemas import CreateProfileRequest, ProfileOut
from app.services.external import enrich_name
from app.services.nl_parser import parse_query
from app.services.queries import ProfileFilters, apply_filters

SORT_COLUMNS = {
    "age": Profile.age,
    "created_at": Profile.created_at,
    "gender_probability": Profile.gender_probability,
}

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _serialize(profile: Profile) -> dict:
    return ProfileOut.model_validate(profile).model_dump(mode="json")


@router.post("")
async def create_profile(
    payload: CreateProfileRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
):
    if payload.name is None or payload.name.strip() == "":
        return error_response(400, "Missing or empty name")

    original = payload.name.strip()

    result = await session.execute(
        select(Profile).where(func.lower(Profile.name) == original.lower())
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": "Profile already exists",
                "data": _serialize(existing),
            },
        )

    enrichment = await enrich_name(client, original)

    profile = Profile(
        name=original,
        gender=enrichment.gender,
        gender_probability=enrichment.gender_probability,
        age=enrichment.age,
        age_group=enrichment.age_group,
        country_id=enrichment.country_id,
        country_name=enrichment.country_name,
        country_probability=enrichment.country_probability,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    return JSONResponse(
        status_code=201,
        content={"status": "success", "data": _serialize(profile)},
    )


@router.get("")
async def list_profiles(
    session: Annotated[AsyncSession, Depends(get_session)],
    gender: str | None = Query(None),
    age_group: str | None = Query(None),
    country_id: str | None = Query(None),
    min_age: int | None = Query(None, ge=0),
    max_age: int | None = Query(None, ge=0),
    min_gender_probability: float | None = Query(None, ge=0, le=1),
    min_country_probability: float | None = Query(None, ge=0, le=1),
    sort_by: Literal["age", "created_at", "gender_probability"] = Query("created_at"),
    order: Literal["asc", "desc"] = Query("asc"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    filters = ProfileFilters(
        gender=gender,
        age_group=age_group,
        country_id=country_id,
        min_age=min_age,
        max_age=max_age,
        min_gender_probability=min_gender_probability,
        min_country_probability=min_country_probability,
    )
    base = apply_filters(select(Profile), filters)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0

    sort_col = SORT_COLUMNS[sort_by]
    ordered = base.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    paged = ordered.limit(limit).offset((page - 1) * limit)

    profiles = (await session.scalars(paged)).all()
    data = [_serialize(p) for p in profiles]

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "page": page,
            "limit": limit,
            "total": total,
            "data": data,
        },
    )


@router.get("/search")
async def search_profiles(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    if q is None or q.strip() == "":
        return error_response(400, "Missing or empty query")

    filters = parse_query(q)
    if not filters.has_any():
        return error_response(400, "Unable to interpret query")

    base = apply_filters(select(Profile), filters)
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar() or 0
    paged = (
        base.order_by(Profile.created_at.asc()).limit(limit).offset((page - 1) * limit)
    )
    profiles = (await session.scalars(paged)).all()
    data = [_serialize(p) for p in profiles]

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "page": page,
            "limit": limit,
            "total": total,
            "data": data,
        },
    )


@router.get("/{profile_id}")
async def get_profile(
    profile_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = await session.get(Profile, profile_id)
    if profile is None:
        return error_response(404, "Profile not found")
    return JSONResponse(
        status_code=200,
        content={"status": "success", "data": _serialize(profile)},
    )


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    profile = await session.get(Profile, profile_id)
    if profile is None:
        return error_response(404, "Profile not found")
    await session.delete(profile)
    await session.commit()
    return Response(status_code=204)
