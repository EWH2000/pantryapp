# pantryapp

A small, LAN-only web app for tracking what's in the kitchen — what we
have, how much, where it lives, and what's running low. Runs on the home
server and is displayed on a wall-mounted (repurposed) iPad in the
kitchen. The iPad is a **dumb display**: it runs nothing but Safari
pointed at a URL on the LAN. All logic and data live on the server.

> **Current state: pre-scaffold.** As of this file's creation the repo
> contains only a git init and a `.venv`. Nothing below the *Stack*
> section exists yet — it describes the agreed design the first build
> session should create. Update this file *as* the skeleton lands so it
> always describes what's actually here, and delete this banner once the
> app runs.

## Why this shape

- **iPad can die and we lose nothing.** No state on the device; it's a
  thin client. Wiping or replacing it costs nothing.
- **"Backup" is copying one file.** All data lives in a single SQLite
  file. Snapshot it, copy it offsite, done.
- **Low blast radius.** Runs as a rootless Podman container on the
  server — sandboxed from the host OS. Nothing here writes outside its
  own folder. (Hard constraint: this project must never expose the home
  network to inbound traffic or risk the host machine.)

## Stack

Decisions made up front (2026-05-30); revisit deliberately, not by drift.

- **Backend: FastAPI** (Python 3.14). Automatic request validation, and
  a free interactive API browser at `/docs` — useful for poking your own
  endpoints while learning.
- **Data: SQLite** via **SQLModel** (one class defines both the DB table
  and its validation; same author as FastAPI). Single file, no DB server.
- **Frontend: Jinja2 server-rendered templates + HTMX.** No JS framework,
  no bundler — plain HTML with HTMX attributes for dynamic updates (e.g.
  re-render the item list on add without a full reload). Same vanilla
  spirit as the author's other project. Hand-written vanilla JS only
  where HTMX doesn't reach.
- **PWA:** a web manifest + service worker so the iPad can "Add to Home
  Screen" and run fullscreen, kiosk-style, with no Safari chrome.
- **Runtime: rootless Podman container** on the home server. A
  `Containerfile` builds the image; the SQLite file lives on a mounted
  volume so data survives rebuilds.
- **Dev loop:** run locally with `uvicorn` + `--reload` on the laptop;
  containerize for deploy to the server. (Python 3.14 is very new — if a
  dependency lacks a wheel, note it here.)

## Scope

- **v1 — pantry only.** Add an item; set quantity, unit, and location
  (pantry / fridge / freezer); mark low / out; search and filter the
  list. Get this genuinely pleasant to *use on a touch screen* before
  adding anything else. Touch targets ≥44px; big tap zones; readable at
  arm's length on the kitchen iPad.
- **v2 (roadmap) — meal ideas.** "What can we make with what we have."
  This pulls in a second data model (recipes + ingredient matching), so
  it's deliberately out of v1.

## Conventions

Seeded; grow this as patterns settle.

- **4-space indentation** everywhere (Python, HTML, CSS, JS).
- **Layout:** `app/` for the FastAPI package, `app/templates/` for Jinja2,
  `app/static/` for CSS/JS/manifest, `app/models.py` for SQLModel tables.
  Adjust as the skeleton lands and document the real layout here.
- **One language front-to-back is Python**; client JS is the exception,
  not the default — reach for HTMX first.
- **Git:** branch → edit → commit → push; never merge without being
  asked. Small, scannable commit subjects. (No remote yet — local-only
  until/unless a private remote is set up.)

## How to run

> _To be filled in once the skeleton exists._ Expected shape:
> `uvicorn app.main:app --reload` for dev; `podman build` + `podman run`
> (with a volume mount for the SQLite file) for the server.

## About the user

- Background in building automation / controls (BACnet, Modbus, Niagara,
  EBO); strong IP networking. Comfortable in a terminal; learning
  software-dev workflows and Git. **Wants to understand what's happening,
  not just have it work** — briefly explain new concepts/commands.
- This is a **partner-facing** app. The partner uses Fedora KDE Plasma,
  is comfortable but won't use a terminal, and will be a primary user of
  the kitchen display. That raises the polish/usability bar: it has to be
  obvious and forgiving to operate by touch, with no jargon.
