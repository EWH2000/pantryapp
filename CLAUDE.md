# pantryapp

A small, LAN-only web app for tracking what's in the kitchen — what we
have, how much, where it lives, and what's running low. Runs on the home
server and is displayed on a wall-mounted (repurposed) iPad in the
kitchen. The iPad is a **dumb display**: it runs nothing but Safari
pointed at a URL on the LAN. All logic and data live on the server.

> **Current state: v1 in progress.** The runnable skeleton landed
> 2026-05-30: add / list / search / filter / mark-status / remove, all
> server-rendered with HTMX. Still deferred from v1: the Podman
> `Containerfile` and the PWA (manifest + service worker). Keep this file
> current as those land.

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
  containerize for deploy to the server. (Python 3.14 wheel check, done
  2026-05-30: fastapi, sqlmodel, `uvicorn[standard]` and all their
  compiled deps — pydantic-core, uvloop, httptools, greenlet — ship cp314
  wheels, so `pip install` needs no compiler. Revisit only if a future
  dep fails to install.)

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
- **Layout** (as built):
  - `app/main.py` — FastAPI app + all routes (`/`, `GET/POST /items`,
    `POST /items/{id}/status`, `DELETE /items/{id}`).
  - `app/models.py` — SQLModel `Item` table + `Location`/`Status` enums.
  - `app/db.py` — SQLite engine, `init_db()`, `get_session()` dependency.
  - `app/templates/` — `base.html`, `index.html`, and `_item_list.html`
    (the list fragment HTMX swaps into `#item-list`; leading `_` = partial).
  - `app/static/css/styles.css`, `app/static/js/htmx.min.js` (vendored —
    **no CDN**, the iPad is LAN-only). Manifest/service worker land here later.
  - `requirements.txt` — direct deps pinned; `pantry.db` is the gitignored
    SQLite file, created automatically on first run.
- **One language front-to-back is Python**; client JS is the exception,
  not the default — reach for HTMX first.
- **Git:** branch → edit → commit → push; never merge without being
  asked. Small, scannable commit subjects. Public remote:
  `github.com/EWH2000/pantryapp`, default branch `main`. Keep all tracked
  files free of personal info (the repo is public).

## How to run

**Dev (laptop):**

```bash
.venv/bin/pip install -r requirements.txt   # first time only
.venv/bin/uvicorn app.main:app --reload     # http://127.0.0.1:8000
```

`--reload` restarts the server whenever you edit a file. The SQLite file
(`pantry.db`) is created automatically on first start. The interactive API
browser is at `/docs`.

**Server (deploy):** rootless Podman container managed by systemd
(Quadlet), data on a persistent named volume, daily SQLite backups, served
on LAN port 8000. Build with `podman build -t pantryapp .`; full runbook in
[`deploy/README.md`](deploy/README.md). The container sets
`PANTRY_DB_PATH=/data/pantry.db` (mounted volume); dev leaves it unset and
uses `./pantry.db`.

## Who it's for

Two everyday users on a wall-mounted kitchen touchscreen — not developers,
not sitting at a desk. One person runs and deploys the app; the other
operates it purely by touch and never sees a command line. That sets the
usability bar: every primary action must be obvious, forgiving, and
jargon-free, with big touch targets, readable at arm's length.
