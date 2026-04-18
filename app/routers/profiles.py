from typing import Annotated

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
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
    name_key = Profile.normalize_name(original)

    result = await session.execute(select(Profile).where(Profile.name_key == name_key))
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
        name_key=name_key,
        gender=enrichment.gender,
        gender_probability=enrichment.gender_probability,
        sample_size=enrichment.sample_size,
        age=enrichment.age,
        age_group=enrichment.age_group,
        country_id=enrichment.country_id,
        country_probability=enrichment.country_probability,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    return JSONResponse(
        status_code=201,
        content={"status": "success", "data": _serialize(profile)},
    )
