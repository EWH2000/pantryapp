"""Database tables for pantryapp.

A SQLModel class is two things at once: a Pydantic model (so FastAPI can
validate incoming form data) AND a SQLAlchemy table (so it maps to a row
in SQLite). We describe the shape of an "item" once, here, and the rest of
the app reuses it for both jobs.
"""

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class Location(str, Enum):
    """Where an item physically lives in the kitchen."""

    pantry = "pantry"
    fridge = "fridge"
    freezer = "freezer"


class Status(str, Enum):
    """How stocked an item is. Drives the color coding in the UI."""

    ok = "ok"      # have plenty
    low = "low"    # running low — buy soon
    out = "out"    # out — buy now


class Category(str, Enum):
    """What role an item plays in a meal — for sorting/filtering."""

    main = "main"      # the centerpiece (meat, mains)
    side = "side"      # sides, veg, starches
    snack = "snack"    # snacks, nibbles


class Item(SQLModel, table=True):
    """One thing in the kitchen we're keeping track of.

    `table=True` is what tells SQLModel to create a real database table
    for this class (not just an in-memory validation model).
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)               # indexed: we search by name
    quantity: float = 1
    unit: str = "pcs"                            # free text, e.g. "g", "L"
    location: Location = Location.pantry
    status: Status = Status.ok
    # Optional: not every staple is a main/side/snack (oil, flour…).
    category: Category | None = Field(default=None, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
