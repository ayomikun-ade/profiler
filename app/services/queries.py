from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func

from app.models import Profile


@dataclass
class ProfileFilters:
    gender: str | None = None
    age_group: str | None = None
    country_id: str | None = None
    min_age: int | None = None
    max_age: int | None = None
    min_gender_probability: float | None = None
    min_country_probability: float | None = None


def apply_filters(stmt: Select[Any], f: ProfileFilters) -> Select[Any]:
    if f.gender is not None:
        stmt = stmt.where(func.lower(Profile.gender) == f.gender.lower())
    if f.age_group is not None:
        stmt = stmt.where(func.lower(Profile.age_group) == f.age_group.lower())
    if f.country_id is not None:
        stmt = stmt.where(func.upper(Profile.country_id) == f.country_id.upper())
    if f.min_age is not None:
        stmt = stmt.where(Profile.age >= f.min_age)
    if f.max_age is not None:
        stmt = stmt.where(Profile.age <= f.max_age)
    if f.min_gender_probability is not None:
        stmt = stmt.where(Profile.gender_probability >= f.min_gender_probability)
    if f.min_country_probability is not None:
        stmt = stmt.where(Profile.country_probability >= f.min_country_probability)
    return stmt
