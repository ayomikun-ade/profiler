"""Rule-based parser that converts natural language queries into ProfileFilters.

Scope (documented in README):
- gender: male/males/man/men/boy/boys/guy/guys | female/females/woman/women/girl/girls/lady/ladies
  (if both a male and female term appear, gender is dropped — matches "male and female ...")
- age_group: child/children/kid(s) | teen(s)/teenager(s) | adult(s) | senior(s)/elderly/elder(s)
- "young" -> min_age=16, max_age=24 (only fills bounds that weren't set explicitly)
- numeric bounds: "above N" | "over N" | "older than N" | "greater than N"   -> min_age=N
                  "below N" | "under N" | "younger than N" | "less than N"   -> max_age=N
                  "age N" | "aged N"                                         -> min_age=max_age=N
- country: matched against pycountry names / common_names plus a small alias table (usa, uk, uae, drc, ...).
"""
import re

import pycountry

from app.services.queries import ProfileFilters

GENDER_MALE_RE = re.compile(r"\b(male|males|man|men|boy|boys|guy|guys)\b", re.IGNORECASE)
GENDER_FEMALE_RE = re.compile(
    r"\b(female|females|woman|women|girl|girls|lady|ladies)\b", re.IGNORECASE
)
YOUNG_RE = re.compile(r"\byoung\b", re.IGNORECASE)
ABOVE_RE = re.compile(
    r"\b(?:above|over|older\s+than|greater\s+than|more\s+than|>=?)\s*(\d+)", re.IGNORECASE
)
BELOW_RE = re.compile(
    r"\b(?:below|under|younger\s+than|less\s+than|<=?)\s*(\d+)", re.IGNORECASE
)
EXACT_AGE_RE = re.compile(r"\b(?:age|aged)\s+(\d+)\b", re.IGNORECASE)

AGE_GROUP_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("child", re.compile(r"\b(child|children|kid|kids)\b", re.IGNORECASE)),
    ("teenager", re.compile(r"\b(teen|teens|teenager|teenagers)\b", re.IGNORECASE)),
    ("adult", re.compile(r"\b(adult|adults)\b", re.IGNORECASE)),
    ("senior", re.compile(r"\b(senior|seniors|elderly|elder|elders)\b", re.IGNORECASE)),
]

COUNTRY_ALIASES: dict[str, str] = {
    "usa": "US", "u.s.a": "US", "u.s.": "US", "america": "US",
    "uk": "GB", "u.k.": "GB", "britain": "GB", "england": "GB", "great britain": "GB",
    "uae": "AE", "emirates": "AE",
    "drc": "CD", "dr congo": "CD", "dr. congo": "CD",
    "south korea": "KR", "north korea": "KP",
    "ivory coast": "CI",
    "czechia": "CZ", "czech republic": "CZ",
    "burma": "MM",
    "russia": "RU",
    "iran": "IR",
    "syria": "SY",
    "venezuela": "VE",
    "bolivia": "BO",
    "moldova": "MD",
    "vietnam": "VN",
    "laos": "LA",
    "tanzania": "TZ",
}


def _build_country_index() -> list[tuple[re.Pattern[str], str]]:
    entries: list[tuple[str, str]] = []
    for country in pycountry.countries:
        code = country.alpha_2
        name = getattr(country, "name", "")
        common = getattr(country, "common_name", None)
        if name:
            entries.append((name.lower(), code))
        if common:
            entries.append((common.lower(), code))
    for alias, code in COUNTRY_ALIASES.items():
        entries.append((alias.lower(), code))
    entries.sort(key=lambda e: len(e[0]), reverse=True)
    return [(re.compile(r"\b" + re.escape(name) + r"\b", re.IGNORECASE), code) for name, code in entries]


_COUNTRY_INDEX = _build_country_index()


def _extract_country(query: str) -> str | None:
    for pattern, code in _COUNTRY_INDEX:
        if pattern.search(query):
            return code
    return None


def parse_query(q: str) -> ProfileFilters:
    filters = ProfileFilters()

    has_female = bool(GENDER_FEMALE_RE.search(q))
    has_male = bool(GENDER_MALE_RE.search(q))
    if has_female and not has_male:
        filters.gender = "female"
    elif has_male and not has_female:
        filters.gender = "male"

    for group, pattern in AGE_GROUP_PATTERNS:
        if pattern.search(q):
            filters.age_group = group
            break

    m = ABOVE_RE.search(q)
    if m:
        filters.min_age = int(m.group(1))
    m = BELOW_RE.search(q)
    if m:
        filters.max_age = int(m.group(1))
    m = EXACT_AGE_RE.search(q)
    if m and filters.min_age is None and filters.max_age is None:
        val = int(m.group(1))
        filters.min_age = val
        filters.max_age = val

    if YOUNG_RE.search(q):
        if filters.min_age is None:
            filters.min_age = 16
        if filters.max_age is None:
            filters.max_age = 24

    filters.country_id = _extract_country(q)

    return filters
