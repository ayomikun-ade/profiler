# Profiler API

FastAPI service that stores demographic profiles and serves them through filtered, sorted, paginated, and natural-language search endpoints.

## Stack
- Python 3.12+ (falls back to a stdlib-only UUIDv7 generator if `uuid.uuid7` isn't available)
- FastAPI + Uvicorn
- SQLAlchemy 2.x async — Postgres (asyncpg) in prod, SQLite (aiosqlite) for local dev
- httpx (upstream enrichment)
- pycountry (country-name ↔ ISO-2 resolution for NL search)

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed         # load the 2026-profile dataset (idempotent)
uvicorn app.main:app --reload
```

Health check: http://localhost:8000/health · OpenAPI docs: http://localhost:8000/docs

Schema is created on startup. `DATABASE_URL` is optional — without it the app writes to a local SQLite file.

## Profile schema

| Field | Type | Notes |
|---|---|---|
| `id` | UUID v7 | Primary key |
| `name` | VARCHAR | Unique |
| `gender` | VARCHAR | `male` or `female` |
| `gender_probability` | FLOAT | |
| `age` | INT | |
| `age_group` | VARCHAR | `child` / `teenager` / `adult` / `senior` |
| `country_id` | VARCHAR(2) | ISO-3166-1 alpha-2 |
| `country_name` | VARCHAR | Full country name |
| `country_probability` | FLOAT | |
| `created_at` | TIMESTAMPTZ | UTC |

Indexes cover every filterable / sortable column (`gender`, `age`, `age_group`, `country_id`, `created_at`, `gender_probability`, `country_probability`) plus the unique index on `name` — keeps list + search responsive on the seeded dataset.

## Endpoints

### `POST /api/profiles`
Body: `{ "name": "ella" }`. Calls Genderize / Agify / Nationalize in parallel, derives `country_name` from `country_id` via pycountry, and stores the result. Returns `201` on new, `200 "Profile already exists"` on idempotent re-post (case + whitespace insensitive). `400` missing/empty, `422` wrong type, `502` on upstream nulls.

### `GET /api/profiles`
Full filtering, sorting, pagination.

**Filters** (all optional, combinable, AND together):
- `gender`, `age_group`, `country_id` — case-insensitive equality
- `min_age`, `max_age` — inclusive integer bounds
- `min_gender_probability`, `min_country_probability` — floats in `[0, 1]`

**Sorting**: `sort_by` ∈ `{ age, created_at, gender_probability }` (default `created_at`) · `order` ∈ `{ asc, desc }` (default `asc`).

**Pagination**: `page` (default 1, min 1) · `limit` (default 10, max 50).

Response:
```json
{ "status": "success", "page": 1, "limit": 10, "total": 2026, "data": [ /* profile */ ] }
```

Invalid parameters return `422 { "status": "error", "message": "Invalid query parameters" }`.

### `GET /api/profiles/search`
Rule-based NL query over the same data.

**Query params**: `q` (required, plain English), `page`, `limit` (same rules as above).

Same response envelope as the list endpoint. `400 "Missing or empty query"` if `q` is absent/blank; `400 "Unable to interpret query"` if the parser extracts no filters.

### `GET /api/profiles/{id}` — `200` / `404`

### `DELETE /api/profiles/{id}` — `204` / `404`

## Natural language parser

Plain-English queries are converted to the same `ProfileFilters` dataclass that the list endpoint uses. Parsing is purely rule-based — regex matches on the lowercased query, word-boundary-aware so partial words don't collide (e.g. `\bmale\b` never matches inside `female`).

### Supported keywords

| Intent | Keywords (word-boundary) | Fills |
|---|---|---|
| Gender = male | `male`, `males`, `man`, `men`, `boy`, `boys`, `guy`, `guys` | `gender=male` |
| Gender = female | `female`, `females`, `woman`, `women`, `girl`, `girls`, `lady`, `ladies` | `gender=female` |
| Age group: child | `child`, `children`, `kid`, `kids` | `age_group=child` |
| Age group: teenager | `teen`, `teens`, `teenager`, `teenagers` | `age_group=teenager` |
| Age group: adult | `adult`, `adults` | `age_group=adult` |
| Age group: senior | `senior`, `seniors`, `elderly`, `elder`, `elders` | `age_group=senior` |
| "young" bucket | `young` | `min_age=16`, `max_age=24` (only fills bounds left open by numeric phrases) |
| Minimum age | `above N`, `over N`, `older than N`, `greater than N`, `more than N`, `>=N`, `> N` | `min_age=N` |
| Maximum age | `below N`, `under N`, `younger than N`, `less than N`, `<=N`, `< N` | `max_age=N` |
| Exact age | `age N`, `aged N` | `min_age=max_age=N` |
| Country | Any pycountry name or `common_name`, plus aliases: `usa`/`america`, `uk`/`britain`/`england`, `uae`/`emirates`, `drc`/`dr congo`, `south korea`, `north korea`, `ivory coast`, `czechia`/`czech republic`, `burma`, `russia`, `iran`, `syria`, `venezuela`, `bolivia`, `moldova`, `vietnam`, `laos`, `tanzania` | `country_id=<ISO-2>` |

### How the logic works

1. Lowercase the query.
2. **Gender** — if both a male-term and female-term match, gender is left unset (matches the spec example `"male and female teenagers above 17"` → no gender filter).
3. **Age group** — first match wins. Order is deterministic (`child`, `teenager`, `adult`, `senior`).
4. **Numeric bounds** — scan for `above/over/...`, `below/under/...`, and `age N` forms. Explicit numbers always win.
5. **"young"** — only fills `min_age`/`max_age` that are still unset. This means `"young adults above 30"` → `age_group=adult, min_age=30, max_age=24` (logically empty set — intentional, user asked for a contradiction).
6. **Country** — a pre-built regex index of every pycountry name + alias is scanned; entries are sorted by length descending so longer phrases beat substrings (e.g. `"united states of america"` wins over `"america"`). Word boundaries prevent e.g. `"niger"` matching inside `"nigeria"`.
7. If no filter field was set, return `400 "Unable to interpret query"`.

### Examples

| Query | Parsed |
|---|---|
| `young males` | `gender=male, min_age=16, max_age=24` |
| `females above 30` | `gender=female, min_age=30` |
| `people from angola` | `country_id=AO` |
| `adult males from kenya` | `gender=male, age_group=adult, country_id=KE` |
| `male and female teenagers above 17` | `age_group=teenager, min_age=17` |
| `senior women from brazil` | `gender=female, age_group=senior, country_id=BR` |
| `kids under 10 from usa` | `age_group=child, max_age=10, country_id=US` |

### Limitations / things the parser does NOT handle

- **No LLM, no grammar tree.** Word order is ignored; `"from kenya young males"` parses the same as `"young males from kenya"`.
- **No negation.** `"not from nigeria"` still resolves to `country_id=NG`. Any `not`/`except`/`excluding` is ignored.
- **Single country per query.** Multiple country mentions collapse to whichever matches first in the index scan (longest name wins); `"from kenya or uganda"` picks one.
- **No OR logic between filters.** All extracted filters are ANDed. `"males or females over 30"` ignores the "or" and ends up with `min_age=30, gender=None` (both present).
- **Numbers must be digits.** `"above thirty"` is not parsed. Only `above 30`.
- **No probability intents.** Phrases like `"high-confidence males"` don't map to `min_gender_probability`. Those have to be passed via the structured filter endpoint.
- **No sorting / pagination intents.** `"top 5 oldest adults"` ignores "top 5" and "oldest". Use `page`/`limit` query params.
- **Country name false-positives in long sentences.** A tangential mention like `"named Chad"` (a first name that's also a country) would extract `country_id=TD`. The parser can't disambiguate proper-noun contexts.
- **Ambiguous age groups.** `"young adults"` fills both `age_group=adult` and the 16–24 bounds — intersection is 20–24. This is usually what you want, but different from `"adults"` alone (no age bounds).
- **Contradictions pass through.** `"young people above 30"` parses to `min_age=30, max_age=24`, which yields zero results. The parser does not detect the contradiction and reject the query.
- **Case of stored values.** `gender` and `age_group` comparisons are already case-insensitive; `country_id` is uppercased before comparison. A DB row with unexpected casing would still match.

## Error shape

All errors return:
```json
{ "status": "error", "message": "<reason>" }
```
Codes used: `400` (missing/empty param, unable to interpret), `404` (profile not found), `422` (`"Invalid query parameters"` for type / range errors on the list/search endpoint, `Invalid body parameter 'name'` on POST), `500`, `502`.

## Deployment

Runs on any platform with a long-lived Python process. Deployed on Railway with a managed Postgres service.

`DATABASE_URL` is read from the environment — Railway supplies `postgresql://...`, which `app/config.py` rewrites to `postgresql+asyncpg://...` before SQLAlchemy sees it.

To seed prod: point `DATABASE_URL` at the Railway Postgres connection string locally and run `python -m scripts.seed`. The seeder is idempotent, so re-running is safe.
