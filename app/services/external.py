import asyncio
from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.classifier import classify_age, pick_top_country
from app.services.countries import country_name_from_code


class UpstreamError(Exception):
    def __init__(self, api_name: str) -> None:
        self.api_name = api_name
        super().__init__(f"{api_name} returned an invalid response")


@dataclass(frozen=True)
class Enrichment:
    gender: str
    gender_probability: float
    age: int
    age_group: str
    country_id: str
    country_name: str
    country_probability: float


async def _get_json(client: httpx.AsyncClient, url: str, name: str, api_name: str) -> dict:
    try:
        resp = await client.get(url, params={"name": name})
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise UpstreamError(api_name) from exc


async def _fetch_genderize(client: httpx.AsyncClient, name: str) -> tuple[str, float]:
    data = await _get_json(client, settings.genderize_url, name, "Genderize")
    gender = data.get("gender")
    count = data.get("count", 0)
    probability = data.get("probability")
    if gender is None or count == 0 or probability is None:
        raise UpstreamError("Genderize")
    return gender, float(probability)


async def _fetch_agify(client: httpx.AsyncClient, name: str) -> int:
    data = await _get_json(client, settings.agify_url, name, "Agify")
    age = data.get("age")
    if age is None:
        raise UpstreamError("Agify")
    return int(age)


async def _fetch_nationalize(client: httpx.AsyncClient, name: str) -> tuple[str, float]:
    data = await _get_json(client, settings.nationalize_url, name, "Nationalize")
    countries = data.get("country") or []
    if not countries:
        raise UpstreamError("Nationalize")
    return pick_top_country(countries)


async def enrich_name(client: httpx.AsyncClient, name: str) -> Enrichment:
    gender_task = _fetch_genderize(client, name)
    agify_task = _fetch_agify(client, name)
    nat_task = _fetch_nationalize(client, name)

    (gender, gender_prob), age, (country_id, country_prob) = await asyncio.gather(
        gender_task, agify_task, nat_task
    )

    return Enrichment(
        gender=gender,
        gender_probability=gender_prob,
        age=age,
        age_group=classify_age(age),
        country_id=country_id,
        country_name=country_name_from_code(country_id),
        country_probability=country_prob,
    )
