"""FastAPI application for pantryapp.

Everything is server-rendered HTML. Each route returns a rendered Jinja2
template — either the whole page (`index.html`) or just the list fragment
(`_item_list.html`). HTMX on the page swaps those fragments in without a
full reload, so there's no hand-written JSON-to-DOM glue.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, select

from app.db import get_session, init_db
from app.models import Item, Location, Status


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook. On startup, ensure the DB tables exist."""
    init_db()
    yield


app = FastAPI(title="pantryapp", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def _all_items(session: Session) -> list[Item]:
    """Every item, sorted by name (case-insensitive) for a stable list."""
    return list(session.exec(select(Item).order_by(Item.name)).all())


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    """The full page: add form, search/filter controls, and the list."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"items": _all_items(session), "locations": list(Location)},
    )


@app.get("/items", response_class=HTMLResponse)
def list_items(
    request: Request,
    q: str = "",
    location: str = "",
    session: Session = Depends(get_session),
):
    """The list fragment, optionally narrowed by search text and location.

    This is the HTMX swap target for #item-list. The search box and the
    location chips both call here; `q` and `location` may be empty.
    """
    statement = select(Item)
    q = q.strip()
    if q:
        # ilike = case-insensitive match; %term% = "contains".
        statement = statement.where(col(Item.name).ilike(f"%{q}%"))
    if location:
        try:
            statement = statement.where(Item.location == Location(location))
        except ValueError:
            pass                        # unknown location → no filter
    items = list(session.exec(statement.order_by(Item.name)).all())
    return templates.TemplateResponse(
        request,
        "_item_list.html",
        {"items": items},
    )


@app.post("/items", response_class=HTMLResponse)
def create_item(
    request: Request,
    name: str = Form(...),
    quantity: float = Form(1),
    unit: str = Form("pcs"),
    location: Location = Form(Location.pantry),
    session: Session = Depends(get_session),
):
    """Add an item from the form, then return the refreshed list."""
    name = name.strip()
    if name:                            # ignore an empty submit, don't error
        session.add(Item(
            name=name,
            quantity=quantity,
            unit=unit.strip() or "pcs",
            location=location,
        ))
        session.commit()
    return templates.TemplateResponse(
        request,
        "_item_list.html",
        {"items": _all_items(session)},
    )


@app.post("/items/{item_id}/status", response_class=HTMLResponse)
def set_status(
    request: Request,
    item_id: int,
    status: Status = Form(...),
    session: Session = Depends(get_session),
):
    """Mark an item have-it / low / out, then return the refreshed list."""
    item = session.get(Item, item_id)
    if item:
        item.status = status
        session.add(item)
        session.commit()
    return templates.TemplateResponse(
        request,
        "_item_list.html",
        {"items": _all_items(session)},
    )


@app.delete("/items/{item_id}", response_class=HTMLResponse)
def delete_item(
    request: Request,
    item_id: int,
    session: Session = Depends(get_session),
):
    """Remove an item, then return the refreshed list."""
    item = session.get(Item, item_id)
    if item:
        session.delete(item)
        session.commit()
    return templates.TemplateResponse(
        request,
        "_item_list.html",
        {"items": _all_items(session)},
    )
