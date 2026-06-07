"""Database engine and per-request session helpers.

SQLite keeps the entire pantry in a single file (`pantry.db`), so a
"backup" is just copying that one file. `init_db()` creates the tables on
startup if they don't exist yet, then applies any lightweight additive
column migrations (see `_ensure_column`) — enough for v1 without Alembic.
`get_session()` hands each web request its own short-lived Session (a unit
of work / transaction) and closes it when the request finishes.
"""

import os
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

# Where the SQLite file lives. In dev it's `pantry.db` in the project root
# (gitignored). In the container, PANTRY_DB_PATH points at a mounted volume
# (e.g. /data/pantry.db) so data survives image rebuilds.
DB_PATH = os.environ.get("PANTRY_DB_PATH", "pantry.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False: SQLite normally refuses to reuse a connection
# across threads, but FastAPI serves requests on a thread pool. This is
# safe here because every request gets its own Session.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create missing tables, then apply additive column migrations.

    `create_all()` only creates *absent* tables; it never ALTERs an existing
    one. So when we add a new column to a model, a database that already has
    real data (the live kitchen DB) won't pick it up. For a nullable, additive
    column SQLite supports a cheap `ALTER TABLE ... ADD COLUMN`, which we run
    idempotently here so a plain container restart applies it — no Alembic, no
    manual SQL the non-technical operator could forget.
    """
    SQLModel.metadata.create_all(engine)
    _ensure_column("item", "barcode", "VARCHAR")
    _migrate_categories()


def _ensure_column(table: str, column: str, ddl_type: str) -> None:
    """Add `column` to `table` if it isn't there yet (SQLite, additive only).

    `table`/`column`/`ddl_type` are our own literals (never user input), so the
    f-string interpolation has no injection surface. A no-op after the first run.
    """
    with engine.begin() as conn:
        cols = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
        if column not in {row[1] for row in cols}:   # row[1] = column name
            conn.exec_driver_sql(
                f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"
            )


def _migrate_categories() -> None:
    """Data fix for the 2026-06-06 category revamp (see `models.Category`).

    The old meal-role values are no longer valid `Category` members, so any row
    still holding one would raise on load. Reclassify them: `main` → `meat`,
    and the dropped `side` → uncategorized (NULL). Raw SQL so it bypasses the
    enum; idempotent — after the first run no rows match.
    """
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE item SET category = 'meat' WHERE category = 'main'")
        conn.exec_driver_sql("UPDATE item SET category = NULL WHERE category = 'side'")


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for one request, then close it."""
    with Session(engine) as session:
        yield session
