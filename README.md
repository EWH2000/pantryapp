# pantryapp

A small, **LAN-only** web app for tracking what's in the kitchen — what we
have, how much, where it lives, and what's running low. It runs on a home
server and is displayed on a wall-mounted, repurposed iPad in the kitchen.
The iPad is a **dumb display**: it runs nothing but Safari pointed at a URL
on the local network. All logic and data live on the server.

> A learning / portfolio project, built deliberately with no front-end
> framework and no build step — just Python, server-rendered HTML, and HTMX.

## Stack

- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.14)
- **Data:** SQLite via [SQLModel](https://sqlmodel.tiangolo.com/) — one
  class defines both the table and its validation; the whole pantry is a
  single file
- **Frontend:** Jinja2 server-rendered templates + [HTMX](https://htmx.org/)
  for dynamic updates — no JS framework, no bundler. HTMX is vendored
  locally (the display device never reaches the internet)
- **Runtime:** rootless Podman container managed by systemd (Quadlet),
  data on a persistent volume, daily backups — see [`deploy/`](./deploy/)

## Features (v1)

- Add an item with quantity, unit, and location (pantry / fridge / freezer)
- Live search by name and filter by location
- Mark each item **Have it / Low / Out** (color-coded at a glance)
- Remove items
- Everything persists to a single SQLite file and survives restarts
- Touch-first UI: large tap targets, readable at arm's length

## Run it (dev)

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

The SQLite file (`pantry.db`) is created automatically on first start.
FastAPI's interactive API browser is at `/docs`.

## Design notes

- **The display is disposable.** No state on the device — wiping or
  replacing the iPad costs nothing.
- **"Backup" is copying one file.** All data lives in one SQLite file.
- **Low blast radius.** Intended to run as a sandboxed rootless container;
  never exposes the home network to inbound internet traffic.

## Status & roadmap

- **v1:** the pantry list above — built, with item categories (main / side /
  snack), and deployable as a rootless Podman service with backups.
- **Next:** adjustable quantities with auto-low coloring, expiration dates,
  recipes + "can I make it?" matching, and PWA support (add-to-home-screen,
  fullscreen kiosk mode). See [`IDEAS.md`](./IDEAS.md) for the running
  idea/friction log.

## License

[MIT](./LICENSE)
