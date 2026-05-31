"""FastAPI application for pantryapp.

Everything is server-rendered HTML. Each route returns a rendered Jinja2
template — either the whole page (`index.html`) or just the list fragment
(`_item_list.html`). HTMX on the page swaps those fragments in without a
full reload, so there's no hand-written JSON-to-DOM glue.
"""

import mimetypes
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, col, select

from app.db import get_session, init_db
from app.models import Category, Item, Location, Status


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook. On startup, ensure the DB tables exist."""
    init_db()
    yield


# Serve the PWA manifest with the correct type; StaticFiles guesses from
# this registry and Python doesn't know .webmanifest by default.
mimetypes.add_type("application/manifest+json", ".webmanifest")


class RevalidatingStaticFiles(StaticFiles):
    """StaticFiles that tells the browser to revalidate before reusing an asset.

    Plain StaticFiles sends an ETag but no Cache-Control, so browsers (Safari
    on the kitchen iPad especially, doubly so once installed as a PWA) fall
    back to *heuristic* caching: they keep a stale copy and don't revalidate.
    That's how a restyle can ship to the server yet the iPad keeps showing the
    old CSS. `no-cache` means "store it, but always check the ETag first" — the
    revalidation is a cheap 304 on the LAN, and a changed file is picked up at
    once. Asset URLs are stable, so this is the right trade for this app.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


app = FastAPI(title="pantryapp", lifespan=lifespan)
app.mount("/static", RevalidatingStaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def _all_items(session: Session) -> list[Item]:
    """Every item, sorted by name (case-insensitive) for a stable list."""
    return list(session.exec(select(Item).order_by(Item.name)).all())


@app.get("/health")
def health():
    """Liveness check for the container healthcheck and monitoring."""
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    """The full page: add form, search/filter controls, and the list."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "items": _all_items(session),
            "locations": list(Location),
            "categories": list(Category),
        },
    )


@app.get("/items", response_class=HTMLResponse)
def list_items(
    request: Request,
    q: str = "",
    location: str = "",
    category: str = "",
    session: Session = Depends(get_session),
):
    """The list fragment, optionally narrowed by search, location, category.

    This is the HTMX swap target for #item-list. The search box and the
    filter chips call here; `q`, `location`, `category` may all be empty.
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
    if category:
        try:
            statement = statement.where(Item.category == Category(category))
        except ValueError:
            pass                        # unknown category → no filter
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
    category: str = Form(""),
    session: Session = Depends(get_session),
):
    """Add an item from the form, then return the refreshed list."""
    name = name.strip()
    if name:                            # ignore an empty submit, don't error
        cat = None
        if category:
            try:
                cat = Category(category)
            except ValueError:
                cat = None              # unknown value → leave uncategorized
        session.add(Item(
            name=name,
            quantity=quantity,
            unit=unit.strip() or "pcs",
            location=location,
            category=cat,
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
