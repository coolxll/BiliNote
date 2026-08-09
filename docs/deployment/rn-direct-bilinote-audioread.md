# rn-direct: BiliNote + Qwen AudioRead deployment

This runbook deploys BiliNote and the Qwen AudioRead API on `rn-direct` as one Docker Compose stack.

## Architecture

| Component | Public endpoint | Host listener | Internal endpoint |
| --- | --- | --- | --- |
| BiliNote | `bilinote.229929605.xyz` | `127.0.0.1:11309` | `nginx:80` |
| AudioRead API | `audioread.229929605.xyz` | `127.0.0.1:11308` | `qwen-audioread-api:8000` |

- Keep `bilinote.229929605.xyz` proxied by Cloudflare.
- Configure `audioread.229929605.xyz` as DNS-only with an A record pointing to `64.188.31.181` so large uploads go directly to Caddy.
- BiliNote calls AudioRead over the Compose network and never uses the public domain.
- Caddy is the only process listening publicly on ports 80 and 443.

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

## 5. Start the stack

```bash
cd /opt/app/bilinote
docker compose config
docker compose pull qwen-audioread-api
docker compose build backend
docker compose build frontend
docker compose up -d
docker compose ps
```

Expected containers:

- `bilinote-backend`
- `bilinote-frontend`
- `bilinote-nginx`
- `qwen-audioread-api`

## 6. Configure Caddy

The checked-in source is `deploy/caddy/bilinote-audioread.caddy`. Add those blocks to `/etc/caddy/Caddyfile`:

```caddy
bilinote.229929605.xyz {
    log {
        output file /var/log/caddy/bilinote.log {
            roll_size 10mb
            roll_keep 3
        }
        format json
    }
    encode zstd gzip
    request_body {
        max_size 10GB
    }
    reverse_proxy 127.0.0.1:11309
}

audioread.229929605.xyz {
    log {
        output file /var/log/caddy/audioread.log {
            roll_size 10mb
            roll_keep 3
        }
        format json
    }
    encode zstd gzip
    request_body {
        max_size 2GB
    }

    @blocked path /ready /docs* /redoc* /openapi.json /api/v1/transcriptions/local*
    respond @blocked 404

    reverse_proxy 127.0.0.1:11308
}
```

Validate before reload:

```bash
sudo install -o caddy -g caddy -m 640 /dev/null /var/log/caddy/bilinote.log
sudo install -o caddy -g caddy -m 640 /dev/null /var/log/caddy/audioread.log
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

## 7. Acceptance tests

```bash
curl -fsS http://127.0.0.1:11308/health
curl -fsS http://127.0.0.1:11309/api/sys_check
curl -fsS https://audioread.229929605.xyz/health
curl -fsS https://bilinote.229929605.xyz/api/sys_check
```

Verify that an unauthenticated API request fails:

```bash
curl -i https://audioread.229929605.xyz/api/v1/jobs
```

Submit a small audio file using the key from `.env`:

```bash
curl -X POST https://audioread.229929605.xyz/api/v1/transcriptions/async \
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

Before an update, record the BiliNote commit and AudioRead image tag:

```bash
git rev-parse HEAD
docker inspect qwen-audioread-api --format '{{.Config.Image}}'
```

Update only to reviewed commits and immutable AudioRead tags, then run the acceptance tests again. To roll back, check out the previous BiliNote commit, restore the previous `QWEN_AUDIOREAD_IMAGE`, and run:

```bash
docker compose pull qwen-audioread-api
docker compose build backend
docker compose build frontend
docker compose up -d
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
- `413`: confirm `audioread.229929605.xyz` is DNS-only and Caddy has the 2 GB request limit.
- AudioRead times out: inspect `docker logs qwen-audioread-api` and the job JSON under `deploy/audioread/data/jobs/`.
- BiliNote reports AudioRead unavailable: run `docker compose exec backend curl -i http://qwen-audioread-api:8000/health`.
- Disk pressure: run the cleanup command manually and inspect `deploy/audioread/data/outputs/`.
