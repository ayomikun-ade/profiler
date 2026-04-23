from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_http_client
from app.errors import error_response
from app.models import Profile
from app.schemas import CreateProfileRequest, ProfileOut
from app.services.external import enrich_name

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
    gender: str | None = None,
    country_id: str | None = None,
    age_group: str | None = None,
):
    stmt = select(Profile)
    if gender is not None:
        stmt = stmt.where(func.lower(Profile.gender) == gender.lower())
    if country_id is not None:
        stmt = stmt.where(func.lower(Profile.country_id) == country_id.lower())
    if age_group is not None:
        stmt = stmt.where(func.lower(Profile.age_group) == age_group.lower())

    result = await session.execute(stmt)
    profiles = result.scalars().all()
    data = [_serialize(p) for p in profiles]
    return JSONResponse(
        status_code=200,
        content={"status": "success", "count": len(data), "data": data},
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
