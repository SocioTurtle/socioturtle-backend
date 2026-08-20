"""One-off data migration: copy all rows from one Postgres database to another.

Used to move off Render's free Postgres (which expires after 30 days) onto a
different host (e.g. Neon) without needing pg_dump/psql installed locally —
this reuses the app's own SQLAlchemy models instead.

Usage:
    SOURCE_DATABASE_URL="postgresql://..." TARGET_DATABASE_URL="postgresql://..." \
        ./.venv/bin/python migrate_db.py

Safe to re-run: rows already present on the target (matched by primary key)
are skipped rather than duplicated.
"""

import os
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CaptchaChallenge, Lead, LeadOtp, NewsletterIssue, Resource, User

# Parents before children, so foreign keys always resolve.
MODELS_IN_ORDER = [User, Resource, Lead, NewsletterIssue, CaptchaChallenge, LeadOtp]


def _normalise(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _reset_sequence(conn, table: str, pk: str) -> None:
    """After inserting explicit integer ids, the table's auto-increment
    sequence hasn't moved — the next natural insert would collide. Point it
    past the highest id we just copied in."""
    conn.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), "
            f"COALESCE((SELECT MAX({pk}) FROM {table}), 1), true)"
        )
    )


def main() -> int:
    source_url = os.environ.get("SOURCE_DATABASE_URL")
    target_url = os.environ.get("TARGET_DATABASE_URL")
    if not source_url or not target_url:
        print("Set SOURCE_DATABASE_URL and TARGET_DATABASE_URL environment variables.", file=sys.stderr)
        return 1

    source_engine = create_engine(_normalise(source_url))
    target_engine = create_engine(_normalise(target_url))

    Base.metadata.create_all(bind=target_engine)

    SourceSession = sessionmaker(bind=source_engine)
    TargetSession = sessionmaker(bind=target_engine)
    src = SourceSession()
    dst = TargetSession()

    try:
        for model in MODELS_IN_ORDER:
            pk_cols = [c.name for c in inspect(model).primary_key]
            columns = [c.name for c in inspect(model).mapper.columns]
            rows = src.query(model).all()

            copied = skipped = 0
            for row in rows:
                pk_values = tuple(getattr(row, c) for c in pk_cols)
                lookup = pk_values[0] if len(pk_values) == 1 else pk_values
                if dst.get(model, lookup) is not None:
                    skipped += 1
                    continue
                data = {c: getattr(row, c) for c in columns}
                dst.add(model(**data))
                copied += 1
            dst.commit()
            print(f"{model.__name__}: copied {copied}, skipped {skipped} (already present)")

        with target_engine.connect() as conn:
            for model in (User, Resource, Lead, NewsletterIssue):
                _reset_sequence(conn, model.__tablename__, "id")
            conn.commit()
    finally:
        src.close()
        dst.close()

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
