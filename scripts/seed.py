"""Idempotently seed the profiles table from seed_profiles.json.

Usage:
    python -m scripts.seed                       # uses ./seed_profiles.json
    python -m scripts.seed path/to/file.json
"""
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Profile


async def seed(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    profiles = payload["profiles"]

    await init_db()

    async with SessionLocal() as session:
        existing = set((await session.scalars(select(Profile.name))).all())
        existing_lower = {n.lower() for n in existing}

        new_rows = [p for p in profiles if p["name"].strip().lower() not in existing_lower]

        if not new_rows:
            print(f"already seeded: {len(profiles)} profiles in file, {len(existing)} in db, 0 inserted")
            return

        session.add_all(
            [
                Profile(
                    name=p["name"].strip(),
                    gender=p["gender"],
                    gender_probability=p["gender_probability"],
                    age=p["age"],
                    age_group=p["age_group"],
                    country_id=p["country_id"],
                    country_name=p["country_name"],
                    country_probability=p["country_probability"],
                )
                for p in new_rows
            ]
        )
        await session.commit()
        print(
            f"inserted {len(new_rows)} profiles "
            f"(skipped {len(profiles) - len(new_rows)} already present)"
        )


def main() -> None:
    default = Path(__file__).resolve().parent.parent / "seed_profiles.json"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not path.exists():
        print(f"seed file not found: {path}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(seed(path))


if __name__ == "__main__":
    main()
