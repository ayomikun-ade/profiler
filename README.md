# Profiler API

FastAPI service that accepts a name, enriches it via Genderize / Agify / Nationalize, persists the result, and serves it back.

## Stack
- Python 3.14 (stdlib `uuid.uuid7`)
- FastAPI + Uvicorn
- SQLAlchemy 2.x async — Postgres (asyncpg) in prod, SQLite (aiosqlite) for local dev
- httpx for upstream calls (fired in parallel via `asyncio.gather`)

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Health check: http://localhost:8000/health · OpenAPI docs: http://localhost:8000/docs

The DB schema is auto-created on startup. With no `DATABASE_URL` set, it writes to a local SQLite file (`profiler.db`).

## Endpoints

All responses use this envelope on success:
```json
{ "status": "success", "data": ... }
```
And this shape on error:
```json
{ "status": "error", "message": "<reason>" }
```

### `POST /api/profiles`
Request:
```json
{ "name": "ella" }
```
`201 Created` — new profile, full payload (`id`, `name`, `gender`, `gender_probability`, `sample_size`, `age`, `age_group`, `country_id`, `country_probability`, `created_at`).

`200 OK` — idempotent hit (same name, case/whitespace-insensitive):
```json
{ "status": "success", "message": "Profile already exists", "data": { ... } }
```

Errors: `400` missing/empty `name`, `422` wrong type, `502` when any upstream returns a null/empty field.

### `GET /api/profiles`
Optional case-insensitive filters: `gender`, `country_id`, `age_group`. Example: `/api/profiles?gender=male&country_id=NG`.

Returns `200` with `count` and a `data` array of `{id, name, gender, age, age_group, country_id}` items.

### `GET /api/profiles/{id}`
`200` with full profile, or `404` if not found.

### `DELETE /api/profiles/{id}`
`204 No Content` on success, or `404` if not found.

## Classification rules
- **Age groups**: 0–12 `child`, 13–19 `teenager`, 20–59 `adult`, 60+ `senior`.
- **Nationality**: country with the highest `probability` from the Nationalize response.

## Error codes
| Code | When |
|-----:|------|
| 400 | `name` missing or empty |
| 404 | Profile not found |
| 422 | Invalid type (e.g. `name` is not a string, malformed UUID in path) |
| 502 | Genderize / Agify / Nationalize returned null/empty |
| 500 | Unhandled server error |

## Deployment
Works on any platform that can run a long-lived Python process. Intended target: Railway with a managed Postgres service (see Stage 8 commit for the Procfile / start command).

Set `DATABASE_URL` to the Postgres connection string, converted from `postgresql://...` to `postgresql+asyncpg://...`.
