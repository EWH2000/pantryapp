"""Database engine and per-request session helpers.

SQLite keeps the entire pantry in a single file (`pantry.db`), so a
"backup" is just copying that one file. `init_db()` creates the tables on
startup if they don't exist yet — no migration tooling needed for v1.
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
    """Create a table for every SQLModel `table=True` class, if missing."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for one request, then close it."""
    with Session(engine) as session:
        yield session
