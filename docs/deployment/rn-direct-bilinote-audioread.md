# rn-direct: BiliNote + Qwen AudioRead deployment

This runbook deploys BiliNote and the Qwen AudioRead API on `rn-direct` as one Docker Compose stack.

## Architecture

| Component | External access | Host listener | Compose endpoint |
| --- | --- | --- | --- |
| BiliNote | Cloudflare Tunnel + Access at `bilinote.229929605.xyz` | `127.0.0.1:11309` | `nginx:80` |
| AudioRead API | None; BiliNote sidecar only | `127.0.0.1:11308` | `qwen-audioread-api:8000` |
| CLIProxyAPI | Managed independently | `127.0.0.1:11304` | `cliproxyapi:8317` |

- Tunnel `rn-direct-bilinote` forwards `bilinote.229929605.xyz` to `http://127.0.0.1:11309`.
- Cloudflare Access requires Google authentication and allows only `coolxll@gmail.com`.
- `audioread.229929605.xyz` must not have a public DNS record or Caddy site block.
- BiliNote calls AudioRead over the Compose network and never uses a public domain.
- BiliNote calls CLIProxyAPI through the existing `cli-proxy-api_default` Docker network, not through a Cloudflare hostname.
- The CLIProxyAPI DNS, Cloudflare, Caddy, and Compose configuration is managed independently and must not be changed by this deployment.
- Both host listeners remain bound to loopback. Caddy continues serving unrelated sites only.

## 1. Publish the AudioRead image

The AudioRead repository is `coolxll/qwen-audioread-api`. Its container workflow publishes immutable tags in this form:

```text
ghcr.io/coolxll/qwen-audioread-api:sha-<short-commit>
```

Push the reviewed AudioRead commit to `main`, wait for the `Build container` workflow, then record the exact `sha-*` tag. Do not deploy `latest` or an unpinned upstream branch.

## 2. Generate the Qianwen auth file locally

Run the interactive login on a workstation with a browser, not on the VPS:

```powershell
cd D:\Workspace\Repository\qwen-audioread-api
$env:PYTHONPATH = "src"
py -3.11 scripts\login_qwen.py --out .auth\qwen-storage-state.json
py -3.11 scripts\convert_to_minimal_auth.py `
  --input .auth\qwen-storage-state.json `
  --out .auth\qwen-audioread-auth.json `
  --force
```

The production file must contain only:

```json
{"tongyi_sso_ticket":"<ticket>"}
```

Never commit either auth file.

## 3. Prepare the server

```bash
ssh rn-direct
sudo mkdir -p /opt/app
sudo chown coolxll:coolxll /opt/app
cd /opt/app
gh repo clone coolxll/BiliNote bilinote
cd /opt/app/bilinote
mkdir -p deploy/audioread/data deploy/audioread/.auth
sudo chown -R 10001:10001 deploy/audioread/data deploy/audioread/.auth
cp .env.example .env
chmod 600 .env
```

Copy the minimal auth file from the workstation:

```powershell
scp D:\Workspace\Repository\qwen-audioread-api\.auth\qwen-audioread-auth.json `
  rn-direct:/tmp/qwen-audioread-auth.json
ssh rn-direct "sudo install -o 10001 -g 10001 -m 600 /tmp/qwen-audioread-auth.json /opt/app/bilinote/deploy/audioread/.auth/qwen-audioread-auth.json && rm /tmp/qwen-audioread-auth.json"
```

## 4. Production environment

Generate the shared API key:

```bash
openssl rand -hex 32
```

Set these values in `/opt/app/bilinote/.env`:

```dotenv
APP_BIND_IP=127.0.0.1
APP_PORT=11309
BACKEND_PORT=8483
BACKEND_HOST=0.0.0.0

ENV=production
TRANSCRIBER_TYPE=qwen-audioread
TASK_MAX_WORKERS=1

BACKEND_MEMORY_LIMIT=1200m
FRONTEND_MEMORY_LIMIT=256m
NGINX_MEMORY_LIMIT=128m

QWEN_AUDIOREAD_IMAGE=ghcr.io/coolxll/qwen-audioread-api:sha-<reviewed-commit>
QWEN_AUDIOREAD_API_KEY=<openssl-output>
QWEN_AUDIOREAD_HOST_PORT=11308
QWEN_AUDIOREAD_POLL_INTERVAL_SECONDS=15
QWEN_AUDIOREAD_POLL_TIMEOUT_SECONDS=1800
QWEN_AUDIOREAD_UPLOAD_TIMEOUT_SECONDS=1800
QWEN_AUDIOREAD_CPU_LIMIT=1.0
QWEN_AUDIOREAD_MEMORY_LIMIT=512m
```

LLM credentials remain managed through the BiliNote provider UI and SQLite database. Do not deploy `chat-proxy` as part of this stack.

For CLIProxyAPI, configure the BiliNote provider with:

```text
Base URL: http://cliproxyapi:8317/v1
Model: qmodel_latest
```

Read the API key from `/opt/app/cli-proxy-api/config.yaml` on the server. Never print it or copy it into this document. The provider configuration is stored in `backend/bili_note.db`.

## 5. Start the stack

```bash
cd /opt/app/bilinote
COMPOSE="docker compose -f docker-compose.yml -f deploy/compose/rn-direct-cliproxy.yml"
$COMPOSE config
docker compose pull qwen-audioread-api
docker compose build backend
docker compose build frontend
$COMPOSE up -d
$COMPOSE ps
```

The external network `cli-proxy-api_default` must already exist. Start the independently managed CLIProxyAPI stack before starting or recreating the BiliNote backend.

Expected containers:

- `bilinote-backend`
- `bilinote-frontend`
- `bilinote-nginx`
- `qwen-audioread-api`

## 6. Configure Cloudflare Tunnel and Access

Create or retain these Cloudflare resources:

- Tunnel: `rn-direct-bilinote`
- Public hostname: `bilinote.229929605.xyz`
- Service: `http://127.0.0.1:11309`
- Access application: `BiliNote`
- Identity provider: Google only
- Allow policy: exact email match for `coolxll@gmail.com`
- Session duration: one week

Run `cloudflared` as a systemd service on `rn-direct` and verify it is enabled:

```bash
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
sudo journalctl -u cloudflared -n 50 --no-pager
```

Do not add BiliNote or AudioRead blocks to `/etc/caddy/Caddyfile`. The checked-in
`deploy/caddy/bilinote-audioread.caddy` records this intentional absence. Before
removing legacy blocks, back up and validate the complete server configuration:

```bash
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.backup-$(date -u +%Y%m%dT%H%M%SZ)
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

## 7. Acceptance tests

```bash
curl -fsS http://127.0.0.1:11308/health
curl -fsS http://127.0.0.1:11309/api/sys_check
curl -I https://bilinote.229929605.xyz/
docker inspect bilinote-backend --format '{{json .NetworkSettings.Networks}}'
```

The external request must return a Cloudflare Access redirect when no Access
session is present. Complete Google login in a browser and verify the BiliNote UI
loads. Confirm AudioRead has no DNS record and is unreachable through Caddy.

Confirm the BiliNote backend can reach CLIProxyAPI without using a public hostname:

```bash
docker compose exec -T backend python - <<'PY'
import sqlite3
import urllib.request

database = sqlite3.connect("/app/bili_note.db")
api_key = database.execute(
    "SELECT api_key FROM providers WHERE name = ? LIMIT 1",
    ("CLIProxyAPI",),
).fetchone()[0]
request = urllib.request.Request(
    "http://cliproxyapi:8317/v1/models",
    headers={"Authorization": f"Bearer {api_key}"},
)
with urllib.request.urlopen(request, timeout=10) as response:
    print(response.status)
PY
```

Then use BiliNote's provider connection test with `qmodel_latest`. A successful test must use `http://cliproxyapi:8317/v1` as the provider base URL.

Test AudioRead over the VPS loopback listener, using the key from `.env`:

```bash
docker compose exec -T backend curl -fsS http://qwen-audioread-api:8000/health
curl -X POST http://127.0.0.1:11308/api/v1/transcriptions/async \
  -H "Authorization: Bearer <api-key>" \
  -F "file=@/path/to/small-audio.mp3" \
  -F "format=md"
```

Poll `/api/v1/jobs/<job_id>` until `succeeded`, download `/api/v1/jobs/<job_id>/file`, then create a BiliNote task with `qwen-audioread` selected. The BiliNote deployment monitor must show AudioRead as authenticated.

## 8. Cleanup timer

Install `deploy/systemd/bilinote-audioread-cleanup.service` as `/etc/systemd/system/bilinote-audioread-cleanup.service`:

```ini
[Unit]
Description=Clean old Qwen AudioRead jobs
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/app/bilinote
ExecStart=/usr/bin/docker compose exec -T qwen-audioread-api python scripts/job_admin.py cleanup --older-than-hours 168 --apply
```

Install `deploy/systemd/bilinote-audioread-cleanup.timer` as `/etc/systemd/system/bilinote-audioread-cleanup.timer`:

```ini
[Unit]
Description=Run Qwen AudioRead cleanup daily

[Timer]
OnCalendar=*-*-* 03:30:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bilinote-audioread-cleanup.timer
```

## 9. Update and rollback

### One-command BiliNote update

Run the reusable deployment script from the local Windows repository:

```powershell
cd E:\App\BiliNote
.\scripts\deploy_rn_direct.ps1
```

Use a local dry run to verify snapshot generation without connecting to or
changing the VPS:

```powershell
.\scripts\deploy_rn_direct.ps1 -DryRun
```

Optional overrides:

```powershell
.\scripts\deploy_rn_direct.ps1 `
  -SshHost rn-direct `
  -RemoteDir /opt/app/bilinote `
  -PublicUrl https://bilinote.229929605.xyz
```

The script:

1. Creates a normalized snapshot from the local Git commit plus current tracked
   and untracked source changes.
2. Includes only `BillNote_frontend/`, application files under `backend/`,
   `nginx/`, `docker-compose.yml`, and `deploy/compose/`.
3. Builds the backend and frontend sequentially in a remote temporary directory
   before changing the live source tree.
4. Synchronizes managed files, including source deletions, then recreates only
   `backend`, `frontend`, and `nginx` with the CLIProxyAPI Compose override.
5. Verifies backend and AudioRead health, CLIProxyAPI access to
   `qmodel_latest`, the unchanged AudioRead container, and the Cloudflare Access
   login redirect.

It never packages `.env`, `backend/bili_note.db`, runtime config, note results,
uploads, screenshots, AudioRead data, or AudioRead authentication. A successful
deployment records its manifest and metadata under `/opt/app/.bilinote-deploy/`.
If a remote build or verification fails, the temporary directory is retained
and its path is printed for diagnosis. Pass `-KeepRemoteStage` to retain it even
after success, or `-SkipPublicAccessCheck` only when intentionally testing
without the Cloudflare Access assertion.

### Manual update and rollback

Before an update, record the BiliNote commit and AudioRead image tag:

```bash
git rev-parse HEAD
docker inspect qwen-audioread-api --format '{{.Config.Image}}'
```

Update only to reviewed commits and immutable AudioRead tags, then run the acceptance tests again. To roll back, check out the previous BiliNote commit, restore the previous `QWEN_AUDIOREAD_IMAGE`, and run:

```bash
COMPOSE="docker compose -f docker-compose.yml -f deploy/compose/rn-direct-cliproxy.yml"
docker compose pull qwen-audioread-api
docker compose build backend
docker compose build frontend
$COMPOSE up -d
```

Do not delete these persistent paths during rollback:

- `backend/bili_note.db`
- `backend/config/`
- `backend/static/`
- `deploy/audioread/data/`
- `deploy/audioread/.auth/`
- `.env`

## 10. Common failures

- `401`: check that BiliNote and AudioRead use the same `QWEN_AUDIOREAD_API_KEY`.
- `AUTH_EXPIRED` or quota errors: regenerate and replace the minimal auth file, then retry a small task.
- `413`: inspect BiliNote nginx and backend upload limits; AudioRead is no longer exposed through Caddy.
- AudioRead times out: inspect `docker logs qwen-audioread-api` and the job JSON under `deploy/audioread/data/jobs/`.
- BiliNote reports AudioRead unavailable: run `docker compose exec backend curl -i http://qwen-audioread-api:8000/health`.
- BiliNote cannot resolve `cliproxyapi`: confirm the backend is attached to `cli-proxy-api_default` and that the CLIProxyAPI stack is running.
- CLIProxyAPI returns `401`: synchronize the BiliNote provider key from `/opt/app/cli-proxy-api/config.yaml` without printing the key.
- Disk pressure: run the cleanup command manually and inspect `deploy/audioread/data/outputs/`.
