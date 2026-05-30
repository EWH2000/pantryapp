"""FastAPI application for pantryapp.

Everything is server-rendered HTML. Each route returns a rendered Jinja2
template — either the whole page (`index.html`) or just the list fragment
(`_item_list.html`). HTMX on the page swaps those fragments in without a
full reload, so there's no hand-written JSON-to-DOM glue.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session, init_db
from app.models import Item, Location


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
def list_items(request: Request, session: Session = Depends(get_session)):
    """Just the list fragment — the HTMX swap target for #item-list."""
    return templates.TemplateResponse(
        request,
        "_item_list.html",
        {"items": _all_items(session)},
    )
