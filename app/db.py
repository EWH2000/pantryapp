"""Database engine and per-request session helpers.

SQLite keeps the entire pantry in a single file (`pantry.db`), so a
"backup" is just copying that one file. `init_db()` creates the tables on
startup if they don't exist yet — no migration tooling needed for v1.
`get_session()` hands each web request its own short-lived Session (a unit
of work / transaction) and closes it when the request finishes.
"""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

# The SQLite file lives in the project root during dev. It's gitignored,
# and in the container it will sit on a mounted volume so data survives
# rebuilds.
DATABASE_URL = "sqlite:///pantry.db"

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
