# NetSim Astra — Deployment Guide

Covers four scenarios:
1. **Local dev machine** — per team (UI, Radio, Constellation)
2. **Admin — full local stack** — all repos, all features, no Docker required
3. **Windows production server** — full stack with Keycloak, NSSM, nginx
4. **Ubuntu server** — Docker-based deployment

---

## Table of Contents

1. [OS Compatibility](#1-os-compatibility)
2. [Prerequisites — All Environments](#2-prerequisites--all-environments)
3. [Local Dev — UI Team](#3-local-dev--ui-team)
4. [Local Dev — Radio Team](#4-local-dev--radio-team)
5. [Local Dev — Constellation Team](#5-local-dev--constellation-team)
6. [Admin — Full Local Stack (All Repos)](#6-admin--full-local-stack-all-repos)
7. [Windows Production Server](#7-windows-production-server)
8. [Ubuntu Server (Docker)](#8-ubuntu-server-docker)
9. [Environment Variables Reference](#9-environment-variables-reference)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. OS Compatibility

| Environment | Supported | Notes |
|-------------|-----------|-------|
| Windows 10/11 (dev) | ✅ | Primary dev OS |
| Windows Server 2019/2022 | ✅ | Production — NSSM + nginx |
| Ubuntu 20.04 / 22.04 | ✅ | Docker-based — recommended for new servers |
| macOS | ✅ | Dev only — same as Linux setup |

> **Short answer: Yes, Ubuntu is supported** — via Docker. The Python code itself is
> cross-platform (no Windows-only dependencies). The NSSM/nginx setup is Windows-only;
> on Ubuntu use Docker Compose instead.

---

## 2. Prerequisites — All Environments

### Python

Python **3.11** is recommended. The codebase runs on 3.10–3.14.

```bash
python --version        # must be 3.10+
pip --version
```

### Git

```bash
git --version           # must be 2.x+
```

### GitHub Access

All repos are private under the `NetsimAstra` org. You need:
- GitHub account added to the appropriate team (`ui`, `radio`, or `constellation`)
- SSH key or HTTPS token configured

```bash
gh auth login           # or configure git credentials manually
```

---

## 3. Local Dev — UI Team

**Repo:** `astra-ui-app`

### Clone and set up

```bash
git clone https://github.com/NetsimAstra/astra-ui-app.git
cd astra-ui-app
pip install -r requirements.txt
```

### Configure

Copy `ToolConfig/keycloak.conf` template and create `settings_private.py`:

```python
# settings_private.py  (do not commit)
CESIUM_TOKEN = "your-cesium-ion-token"   # from cesium.com/ion
N2YO_API_KEY = ""                         # optional — for live satellite mode
```

Get a free Cesium Ion token at `https://cesium.com/ion/tokens`.

### CesiumJS library

The 3D globe requires the CesiumJS library. Download and place it at `Cesium/` in the repo root:

```bash
# Option A: CDN (set in settings_private.py — no local download needed)
# Option B: Download from https://cesium.com/downloads/ and extract to Cesium/
```

### Run

```bash
DEV_AUTH_BYPASS=1 FLASK_SECRET=dev-secret python satellite_planner.py
```

Open `http://localhost:8000` in your browser.

`DEV_AUTH_BYPASS=1` skips Keycloak login. A fake user `dev-local-user` is injected.
Projects are saved to `projects/dev-local-user/`.

### Run tests

```bash
FLASK_SECRET=test-secret TESTING=1 python -m pytest tests/ --ignore=tests/e2e -v
```

---

## 4. Local Dev — Radio Team

**Repo:** `astra-radio-engine`

### Clone and set up

```bash
git clone https://github.com/NetsimAstra/astra-radio-engine.git
cd astra-radio-engine
pip install -r requirements.txt
```

> **rasterio on Windows**: If `pip install rasterio` fails, install from a wheel:
> ```bash
> pip install rasterio --find-links https://girder.github.io/large_image_wheels
> ```

### Run the health endpoint

```bash
python app.py
curl http://localhost:8010/health
# {"status": "ok", "service": "radio-engine"}
```

### Run tests

```bash
python -m pytest tests/ -v
python -m pytest tests/integration/ -v
```

### WorldCover clutter data (optional)

Clutter loss calculations use ESA WorldCover raster tiles. Without them, a fallback value
is used. To download tiles for India:

```bash
python download_india_tiles.py    # from astra-data repo
```

Set `WORLDCOVER_DIR` env var to the download directory.

---

## 5. Local Dev — Constellation Team

**Repo:** `astra-constellation-engine`

### Clone and set up

```bash
git clone https://github.com/NetsimAstra/astra-constellation-engine.git
cd astra-constellation-engine
pip install -r requirements.txt
```

### Optional: N2YO API key (for live satellite mode)

```bash
export N2YO_TOKEN=your-n2yo-api-key    # or set in env
```

Get a free key at `https://www.n2yo.com/api/`.

### Run the health endpoint

```bash
python app.py
curl http://localhost:8020/health
# {"status": "ok", "service": "constellation-engine"}
```

### Run tests

```bash
python -m pytest tests/ -v
python -m pytest tests/integration/ -v
```

---

## 6. Admin — Full Local Stack (All Repos)

Use this if you are a **platform admin** who has all repos cloned and wants every feature
working on a single machine — no Docker, no Keycloak, no cloud dependencies.

> **Architecture note:** The UI app (`astra-ui-app`) currently contains transition copies of
> the engine source files and runs all computation in-process. Running all three services
> is therefore optional right now but is the correct setup for validating the full service
> topology before HTTP migration.

### 6.1 Clone all repos

```bash
mkdir D:\NetSim-astra      # or any folder of your choice
cd D:\NetSim-astra

git clone https://github.com/NetsimAstra/astra-ui-app.git
git clone https://github.com/NetsimAstra/astra-radio-engine.git
git clone https://github.com/NetsimAstra/astra-constellation-engine.git
git clone https://github.com/NetsimAstra/astra-data.git
git clone https://github.com/NetsimAstra/astra-integration.git   # optional — docker-compose only
git clone https://github.com/NetsimAstra/astra-docs.git          # optional — documentation
```

### 6.2 Install dependencies for all services

```bash
pip install -r astra-ui-app/requirements.txt
pip install -r astra-radio-engine/requirements.txt
pip install -r astra-constellation-engine/requirements.txt
```

> **rasterio on Windows** — if the above fails for `rasterio`:
> ```bash
> pip install rasterio --find-links https://girder.github.io/large_image_wheels
> ```

### 6.3 Copy boundary data into the UI app

The boundary GeoJSON files (India, USA, Japan + states) live in `astra-data`.
Copy them into `astra-ui-app` so the form dropdowns work:

```bash
# Windows (cmd)
xcopy /E /Y D:\NetSim-astra\astra-data\data\boundaries D:\NetSim-astra\astra-ui-app\data\boundaries\

# Git Bash / Linux
cp -r astra-data/data/boundaries astra-ui-app/data/
```

### 6.4 Configure settings

Create `astra-ui-app/settings_private.py` (not committed — keep local):

```python
# astra-ui-app/settings_private.py
CESIUM_TOKEN = "your-cesium-ion-token"    # https://cesium.com/ion/tokens  (free tier works)
N2YO_API_KEY = ""                          # https://www.n2yo.com/api/  (optional — for live modes)
```

> Without `CESIUM_TOKEN` the 3D globe loads with default Bing imagery only.
> Without `N2YO_API_KEY` live satellite modes fall back to CelesTrak (free, no key needed).

### 6.5 Run all three services

Open **three separate terminals** (or use Windows Terminal tabs):

**Terminal 1 — Constellation Engine (port 8020)**

```bash
cd D:\NetSim-astra\astra-constellation-engine
python app.py
# → Serving on http://localhost:8020
```

**Terminal 2 — Radio Engine (port 8010)**

```bash
cd D:\NetSim-astra\astra-radio-engine
python app.py
# → Serving on http://localhost:8010
```

**Terminal 3 — UI App (port 8000)**

```bash
cd D:\NetSim-astra\astra-ui-app
DEV_AUTH_BYPASS=1 FLASK_SECRET=dev-secret python satellite_planner.py
# → Serving on http://localhost:8000
```

`DEV_AUTH_BYPASS=1` skips Keycloak — a fake user `dev-local-user` is injected automatically.
Projects are saved to `astra-ui-app/projects/dev-local-user/`.

### 6.6 Optional: single startup script

Save as `D:\NetSim-astra\start-local.bat`:

```bat
@echo off
echo Starting Constellation Engine on :8020 ...
start "Constellation" cmd /k "cd /d D:\NetSim-astra\astra-constellation-engine && python app.py"

echo Starting Radio Engine on :8010 ...
start "Radio" cmd /k "cd /d D:\NetSim-astra\astra-radio-engine && python app.py"

echo Starting UI App on :8000 ...
start "UI" cmd /k "cd /d D:\NetSim-astra\astra-ui-app && set DEV_AUTH_BYPASS=1 && set FLASK_SECRET=dev-secret && python satellite_planner.py"

echo All services starting. Open http://localhost:8000
```

Run it: double-click `start-local.bat` or execute from any terminal.

### 6.7 Verify all services

```bash
curl http://localhost:8010/health   # {"status":"ok","service":"radio-engine"}
curl http://localhost:8020/health   # {"status":"ok","service":"constellation-engine"}
curl http://localhost:8000/         # HTTP 200 — main form page
```

### 6.8 Full feature checklist

| Feature | Mode | How to test |
|---------|------|-------------|
| Synthetic point analysis | 1 | Form → Synthetic → Point → Submit |
| Synthetic coverage heatmap | 2 | Form → Synthetic → Coverage → Submit |
| Live point analysis | 3 | Form → Live → Point → Submit (needs internet) |
| Live coverage heatmap | 4 | Form → Live → Coverage → Submit (needs internet) |
| Satellite footprint | 5 | Form → Synthetic → Footprint → Submit |
| Coverage replay | 4R | Complete a live coverage run → Replay |
| Multibeam CINR | 2M | Form → GEO → Coverage → Enable multibeam → Submit |
| Save / load project | — | Submit any job → Save Project → Load it back |
| CSV download | — | Any completed job → Download CSV |
| CLI batch run | — | `python cli.py run tests/configs/cli/point_*.json` |

### 6.9 WorldCover clutter data (optional — improves accuracy)

Without WorldCover, clutter loss falls back to a constant. To enable full clutter:

```bash
# Clone astra-data if not done
cd D:\NetSim-astra\astra-data

# Download India tiles (~2 GB)
python utilities/download_india_tiles.py

# Set env var before starting radio engine
set WORLDCOVER_DIR=D:\NetSim-astra\astra-data\data\worldcover
```

### 6.10 Run tests across all repos

```bash
# UI tests
cd D:\NetSim-astra\astra-ui-app
FLASK_SECRET=test-secret TESTING=1 python -m pytest tests/ --ignore=tests/e2e -v

# Radio engine tests
cd D:\NetSim-astra\astra-radio-engine
python -m pytest tests/ -v

# Constellation engine tests
cd D:\NetSim-astra\astra-constellation-engine
python -m pytest tests/ -v
```

---

## 7. Windows Production Server

### 7.1 Prerequisites

Install these on the server before anything else:

| Tool | Version | Download |
|------|---------|----------|
| Python | 3.11 | https://python.org/downloads/ |
| Git for Windows | Latest | https://git-scm.com/download/win |
| NSSM | 2.24 | https://nssm.cc/download |
| nginx | Latest stable | https://nginx.org/en/download.html |

**Install NSSM:**
1. Download `nssm-2.24.zip`
2. Extract and copy `nssm.exe` (64-bit) to `C:\Windows\System32\`
3. Verify: `nssm version`

**Install nginx:**
1. Download and extract to `C:\nginx\`
2. Install as a service: `nssm install nginx C:\nginx\nginx.exe`
3. Start: `nssm start nginx`

### 7.2 Clone all repos

```cmd
mkdir C:\app
git clone https://github.com/NetsimAstra/astra-ui-app.git         C:\app\ui
git clone https://github.com/NetsimAstra/astra-radio-engine.git    C:\app\radio
git clone https://github.com/NetsimAstra/astra-constellation-engine.git C:\app\constellation
git clone https://github.com/NetsimAstra/astra-integration.git    C:\app\integration
git clone https://github.com/NetsimAstra/astra-data.git            C:\app\data
```

### 7.3 Install Python dependencies

```cmd
pip install -r C:\app\ui\requirements.txt
pip install -r C:\app\radio\requirements.txt
pip install -r C:\app\constellation\requirements.txt
```

> **rasterio on Windows Server**: install from wheel if pip fails:
> ```cmd
> pip install rasterio --find-links https://girder.github.io/large_image_wheels
> ```

### 7.4 Copy boundary data

```cmd
xcopy /E /Y C:\app\data\data\boundaries C:\app\ui\data\boundaries\
```

### 7.5 Create settings_private.py

```cmd
notepad C:\app\ui\settings_private.py
```

```python
CESIUM_TOKEN = "your-cesium-ion-token"
N2YO_API_KEY = "your-n2yo-key-or-empty"
```

### 7.6 Install services with NSSM

Install each service. Run in **Admin CMD**:

```cmd
cd C:\

REM --- Constellation Engine (port 8020) ---
nssm install netsim-constellation C:\Python311\python.exe
nssm set netsim-constellation AppDirectory C:\app\constellation
nssm set netsim-constellation AppParameters app.py
nssm set netsim-constellation AppStdout C:\app\constellation\logs\stdout.log
nssm set netsim-constellation AppStderr C:\app\constellation\logs\stderr.log
nssm set netsim-constellation AppEnvironmentExtra ^
    N2YO_TOKEN=your-n2yo-key

REM --- Radio Engine (port 8010) ---
nssm install netsim-radio C:\Python311\python.exe
nssm set netsim-radio AppDirectory C:\app\radio
nssm set netsim-radio AppParameters app.py
nssm set netsim-radio AppStdout C:\app\radio\logs\stdout.log
nssm set netsim-radio AppStderr C:\app\radio\logs\stderr.log
nssm set netsim-radio AppEnvironmentExtra ^
    WORLDCOVER_DIR=C:\app\data\worldcover

REM --- UI App (port 8000) ---
nssm install netsim-astra C:\Python311\python.exe
nssm set netsim-astra AppDirectory C:\app\ui
nssm set netsim-astra AppParameters satellite_planner.py
nssm set netsim-astra AppStdout C:\app\ui\logs\stdout.log
nssm set netsim-astra AppStderr C:\app\ui\logs\stderr.log
nssm set netsim-astra AppEnvironmentExtra ^
    FLASK_SECRET=your-random-secret-64-chars ^
    PUBLIC_HOST=your-domain.com ^
    KC_CLIENT_SECRET=your-keycloak-client-secret ^
    CESIUM_TOKEN=your-cesium-token ^
    N2YO_TOKEN=your-n2yo-key
```

Generate `FLASK_SECRET`:
```cmd
python -c "import secrets; print(secrets.token_hex(32))"
```

### 7.7 Create log directories

```cmd
mkdir C:\app\ui\logs
mkdir C:\app\radio\logs
mkdir C:\app\constellation\logs
```

### 7.8 Configure Keycloak

1. Log in to Keycloak admin at `https://auth.your-domain.com/auth/admin/`
2. Realm: `Tetcos`
3. Client ID: `heatmap-web`
4. Add redirect URIs:
   ```
   https://your-domain.com/*
   https://your-domain.com/callback
   ```
5. Copy the **Client Secret** → use as `KC_CLIENT_SECRET`

### 7.9 Configure nginx

Edit `C:\nginx\conf\nginx.conf`:

```nginx
http {
    server {
        listen 443 ssl;
        server_name your-domain.com;

        ssl_certificate     C:/certs/fullchain.pem;
        ssl_certificate_key C:/certs/privkey.pem;

        # UI App
        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_read_timeout 300s;
        }

        # Radio Engine (internal only — not exposed to internet)
        # location /radio/ { proxy_pass http://127.0.0.1:8010/; }

        # Constellation Engine (internal only)
        # location /constellation/ { proxy_pass http://127.0.0.1:8020/; }
    }

    # Redirect HTTP to HTTPS
    server {
        listen 80;
        server_name your-domain.com;
        return 301 https://$host$request_uri;
    }
}
```

Test and reload:
```cmd
nginx -t
nssm restart nginx
```

### 7.10 Start all services

```cmd
nssm start netsim-constellation
nssm start netsim-radio
nssm start netsim-astra
```

Verify all running:
```cmd
sc query netsim-constellation
sc query netsim-radio
sc query netsim-astra
```

All should show `STATE: 4 RUNNING`.

### 7.11 Verify

```cmd
curl http://127.0.0.1:8010/health    & REM radio
curl http://127.0.0.1:8020/health    & REM constellation
curl http://127.0.0.1:8000/          & REM UI (will redirect to Keycloak)
```

Open `https://your-domain.com` in a browser — should redirect to Keycloak login.

### 7.12 Management server (optional)

The manage server allows deploy-admins to pull updates and rollback via a web UI.
See `deploy/DEPLOYMENT.md` in `astra-docs` for the full management server setup.

---

## 8. Ubuntu Server (Docker)

This is the **recommended approach** for new Ubuntu servers.

### 8.1 Prerequisites

```bash
# Docker Engine
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Docker Compose plugin
sudo apt-get install docker-compose-plugin

# Verify
docker --version
docker compose version
```

### 8.2 Clone integration repo

```bash
git clone https://github.com/NetsimAstra/astra-integration.git
cd astra-integration
```

### 8.3 Configure environment

```bash
cp .env.example .env
nano .env
```

Fill in:
```env
FLASK_SECRET=your-random-secret-64-chars
PUBLIC_HOST=your-domain.com
KC_CLIENT_SECRET=your-keycloak-client-secret
CESIUM_TOKEN=your-cesium-token
N2YO_TOKEN=your-n2yo-key
```

Generate `FLASK_SECRET`:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 8.4 Pull images and start

```bash
docker compose pull
docker compose up -d
```

Images are pulled from GitHub Container Registry:
- `ghcr.io/netsimastra/astra-radio-engine:latest`
- `ghcr.io/netsimastra/astra-constellation-engine:latest`
- `ghcr.io/netsimastra/astra-ui-app:latest`

### 8.5 Verify

```bash
curl http://localhost:8010/health    # radio
curl http://localhost:8020/health    # constellation
curl http://localhost:8000/          # UI
```

### 8.6 nginx reverse proxy (Ubuntu)

```bash
sudo apt-get install nginx certbot python3-certbot-nginx

# Get SSL cert
sudo certbot --nginx -d your-domain.com

# Create proxy config
sudo nano /etc/nginx/sites-available/netsim-astra
```

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    # certbot fills in ssl_certificate lines

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/netsim-astra /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 8.7 Auto-restart on reboot

```bash
sudo systemctl enable docker
# docker compose services already restart via restart policy in docker-compose.yml
```

To add restart policy, edit `docker-compose.yml`:
```yaml
services:
  ui-app:
    restart: unless-stopped
  radio-engine:
    restart: unless-stopped
  constellation-engine:
    restart: unless-stopped
```

### 8.8 Update to latest version

```bash
cd astra-integration
docker compose pull
docker compose up -d
```

---

## 9. Environment Variables Reference

| Variable | Required | Used by | Description |
|----------|----------|---------|-------------|
| `FLASK_SECRET` | ✅ Production | UI | Flask session signing key (min 32 chars random) |
| `PUBLIC_HOST` | ✅ Production | UI | Public hostname for Keycloak redirect URLs |
| `KC_CLIENT_SECRET` | ✅ Production | UI | Keycloak OIDC client secret |
| `DEV_AUTH_BYPASS` | Dev only | UI | Set `1` to skip Keycloak on localhost |
| `CESIUM_TOKEN` | Recommended | UI | CesiumJS Ion API token |
| `N2YO_TOKEN` | Optional | Constellation | N2YO live satellite API key |
| `WORLDCOVER_DIR` | Optional | Radio | Path to ESA WorldCover raster tiles |
| `TESTING` | CI only | UI | Set `1` to bypass `login_required` in tests |
| `PORT` | Optional | UI | Override default port 8000 |
| `MAX_GRID_POINTS` | Optional | UI | Override max coverage grid points (default 20000) |

---

## 10. Troubleshooting

### App doesn't start — `FLASK_SECRET` error

```
RuntimeError: FLASK_SECRET environment variable is required
```

Set it: `FLASK_SECRET=any-random-string python satellite_planner.py`

For tests: `FLASK_SECRET=test-secret TESTING=1 python -m pytest ...`

### Cesium globe is blank / black screen

- Check `CESIUM_TOKEN` is set and valid
- Open browser console — look for 401 errors from `api.cesium.com`
- Get a token at `https://cesium.com/ion/tokens`

### No live satellites appear (Mode 3/4/6)

- Check `N2YO_TOKEN` is set
- Try switching source to **CelesTrak** (no API key needed) in the form
- Check elevation angle — try lowering minimum elevation to 5°

### No coverage data / empty heatmap

- Check elevation angle vs satellite altitude
- Try a larger region (increase span)
- Check progress panel for error messages

### Port already in use

```bash
# Windows
netstat -ano | findstr :8000
taskkill /F /PID <pid>

# Linux/Docker
lsof -i :8000
kill -9 <pid>
```

### rasterio install fails on Windows

```bash
pip install rasterio --find-links https://girder.github.io/large_image_wheels
```

### Docker images not found (GHCR)

Log in to GHCR first:
```bash
echo YOUR_GHCR_TOKEN | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
docker compose pull
```

### Keycloak redirect loop

- Check `PUBLIC_HOST` matches exactly the hostname in the browser URL
- Check `KC_CLIENT_SECRET` is correct
- Check redirect URIs in Keycloak client settings include `https://your-domain.com/*`

### Windows service won't start (NSSM)

```cmd
nssm status netsim-astra
type C:\app\ui\logs\stderr.log
```

Common cause: wrong Python path or missing env var. Re-check `nssm get netsim-astra AppEnvironmentExtra`.

---

*Last updated: 2026-03-20 — added Section 6: Admin Full Local Stack*
