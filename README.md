# OCI Tree View

An interactive web UI that renders your Oracle Cloud Infrastructure as a navigable tree. Resources across all configured regions and compartments are displayed hierarchically, each with a direct link into the OCI console, creation date, OCID (click to copy), and a detail panel. Backup status (including failures and missing-backup indicators) is surfaced at the compartment level.

Configured regions: `eu-frankfurt-1`, `eu-stockholm-1`.

## Prerequisites

- Docker + Docker Compose
- A valid OCI config at `~/.oci/config`  
  Key file paths inside that config **must** use `/root/.oci/...` (the container runs as root)

## Running

```sh
docker compose up -d --build
```

| Service  | URL                    |
|----------|------------------------|
| Frontend | http://localhost:3010  |
| Backend  | http://localhost:8010  |

The backend caches the full tree in memory. Hit **Reload** in the UI (or `GET /api/tree?force=true`) to refresh.

> **Note:** If you add or update frontend dependencies, run `npm install` inside `frontend/` and commit the updated `package-lock.json` before rebuilding.

## Running without Docker

```sh
./start-backend.sh   # FastAPI on :8010 (creates .venv automatically)
./start-frontend.sh  # React dev server on :3010
```

## Auto-start at WSL boot (systemd)

Make sure systemd is enabled in WSL (`/etc/wsl.conf` should contain `systemd=true`), then:

```sh
sudo cp ocitreeview@.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ocitreeview@$USER
```

The `@$USER` suffix tells systemd to run the service as your user, with the working directory set to `/home/$USER/ocitreeview`. Anyone who checks out this repo just substitutes their own username.

To stop / disable:

```sh
sudo systemctl stop ocitreeview@$USER
sudo systemctl disable ocitreeview@$USER
```
