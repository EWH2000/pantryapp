# Deploying pantryapp (rootless Podman + systemd)

Runs pantryapp as an always-on, rootless container managed by systemd
(Quadlet), with data on a persistent volume and daily backups. Tested on
Fedora with Podman 5.8 and Python 3.14.

## What's here

| File | Purpose |
|------|---------|
| `../Containerfile` | Builds the image (`python:3.14-slim`, non-root, prod uvicorn) |
| `pantryapp.container` | Quadlet unit → systemd service for the container |
| `backup.sh` | Consistent SQLite snapshot to a host folder |
| `pantryapp-backup.service` / `.timer` | Daily backup via systemd |

## One-time setup

### 1. Build the image

```bash
cd ..                       # repo root (where the Containerfile is)
podman build -t pantryapp:latest .
```

### 2. Install & start the service

```bash
mkdir -p ~/.config/containers/systemd
cp deploy/pantryapp.container ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start pantryapp.service
systemctl --user status pantryapp.service   # should be active (running)
```

The app is now on `http://127.0.0.1:8000`. A named volume `pantrydata`
holds the SQLite database at `/data/pantry.db` inside the container.

### 3. Keep it running headless (requires sudo)

By default a user's services stop when they log out. To keep the container
running across logout/reboot:

```bash
sudo loginctl enable-linger "$USER"
```

`WantedBy=default.target` in the unit then starts it automatically on boot.
(Run `systemctl --user enable pantryapp.service` once so it's wanted.)

### 4. Open the firewall (requires sudo)

```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

Now reachable on the LAN at `http://<server-ip>:8000`.

### 5. Enable daily backups

```bash
cp deploy/backup.sh ~/.local/bin/pantryapp-backup.sh
chmod +x ~/.local/bin/pantryapp-backup.sh
cp deploy/pantryapp-backup.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now pantryapp-backup.timer
systemctl --user list-timers pantryapp-backup.timer   # confirm next run
```

Snapshots land in `~/.local/share/pantryapp/backups/` (newest 14 kept).
Copy that folder offsite for a real backup.

## Day-to-day

```bash
# Logs
journalctl --user -u pantryapp.service -f

# Health / status
podman ps
systemctl --user status pantryapp.service

# Manual backup right now
~/.local/bin/pantryapp-backup.sh
```

## Updating to a new version

```bash
git pull
podman build -t pantryapp:latest .
systemctl --user restart pantryapp.service   # data is on the volume, safe
```

## Restoring from a backup

```bash
systemctl --user stop pantryapp.service
# copy a snapshot back into the volume as the live DB
podman run --rm -v pantrydata:/data -v ~/.local/share/pantryapp/backups:/b:ro,Z \
    docker.io/library/python:3.14-slim \
    cp /b/pantry-YYYYMMDD-HHMMSS.db /data/pantry.db
systemctl --user start pantryapp.service
```

## Notes

- **Rootless:** the container runs as your user (mapped via subuid/subgid),
  so a container compromise can't reach the host as root.
- **Port 8000** is published to the LAN only; the app never reaches the
  internet and nothing inbound is exposed beyond this port.
- The dev loop is unaffected: `uvicorn app.main:app --reload` from the repo
  root still uses a local `./pantry.db` (the container sets `PANTRY_DB_PATH`).
