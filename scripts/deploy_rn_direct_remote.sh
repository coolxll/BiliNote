#!/usr/bin/env bash
set -Eeuo pipefail

REMOTE_DIR=""
STAGE_DIR=""
PUBLIC_URL=""
EXPECTED_ARCHIVE_SHA256=""
LOCAL_HEAD=""
KEEP_STAGE=0
SKIP_PUBLIC_ACCESS_CHECK=0
DEPLOY_SUCCEEDED=0

log() {
    printf '\n==> %s\n' "$1"
}

die() {
    printf 'ERROR: %s\n' "$1" >&2
    exit 1
}

while (($# > 0)); do
    case "$1" in
        --remote-dir)
            REMOTE_DIR="$2"
            shift 2
            ;;
        --stage-dir)
            STAGE_DIR="$2"
            shift 2
            ;;
        --public-url)
            PUBLIC_URL="$2"
            shift 2
            ;;
        --archive-sha256)
            EXPECTED_ARCHIVE_SHA256="$2"
            shift 2
            ;;
        --local-head)
            LOCAL_HEAD="$2"
            shift 2
            ;;
        --keep-stage)
            KEEP_STAGE=1
            shift
            ;;
        --skip-public-access-check)
            SKIP_PUBLIC_ACCESS_CHECK=1
            shift
            ;;
        *)
            die "Unknown argument: $1"
            ;;
    esac
done

[[ -n "$REMOTE_DIR" ]] || die "--remote-dir is required"
[[ -n "$STAGE_DIR" ]] || die "--stage-dir is required"
[[ -n "$PUBLIC_URL" ]] || die "--public-url is required"
[[ -n "$EXPECTED_ARCHIVE_SHA256" ]] || die "--archive-sha256 is required"
[[ -n "$LOCAL_HEAD" ]] || die "--local-head is required"
[[ "$REMOTE_DIR" == /* && "$REMOTE_DIR" != "/" ]] || die "Remote directory must be an absolute non-root path"
[[ "$STAGE_DIR" == /tmp/bilinote-deploy-* ]] || die "Unexpected staging directory: $STAGE_DIR"

ARCHIVE="$STAGE_DIR/source.tar"
MANIFEST="$STAGE_DIR/managed-files.txt"
HELPER="$STAGE_DIR/deploy_remote.sh"
NORMALIZED_MANIFEST="$STAGE_DIR/managed-files.normalized.txt"
SOURCE_DIR="$STAGE_DIR/source"
STATE_DIR="$(dirname "$REMOTE_DIR")/.bilinote-deploy"
PREVIOUS_MANIFEST="$STATE_DIR/managed-files.txt"
CANDIDATES="$STAGE_DIR/managed-candidates.txt"
STALE_FILES="$STAGE_DIR/stale-files.txt"

cleanup() {
    if [[ "$DEPLOY_SUCCEEDED" == "1" && "$KEEP_STAGE" == "0" ]]; then
        rm -rf -- "$STAGE_DIR"
    elif [[ "$KEEP_STAGE" == "1" || "$DEPLOY_SUCCEEDED" != "1" ]]; then
        printf '\nRemote staging directory retained: %s\n' "$STAGE_DIR"
    fi
}
trap cleanup EXIT

for command_name in docker python3 tar sha256sum curl git; do
    command -v "$command_name" >/dev/null 2>&1 || die "Required command is missing: $command_name"
done

[[ -d "$REMOTE_DIR" ]] || die "Remote repository does not exist: $REMOTE_DIR"
[[ -f "$REMOTE_DIR/.env" ]] || die "Persistent environment file is missing: $REMOTE_DIR/.env"
[[ -f "$REMOTE_DIR/backend/bili_note.db" ]] || die "Persistent database is missing: $REMOTE_DIR/backend/bili_note.db"
[[ -f "$REMOTE_DIR/deploy/audioread/.auth/qwen-audioread-auth.json" ]] || die "AudioRead authentication file is missing"
[[ -f "$ARCHIVE" ]] || die "Source archive is missing"
[[ -f "$MANIFEST" ]] || die "Managed file manifest is missing"
[[ -f "$HELPER" ]] || die "Remote helper is missing"

tr -d '\r' < "$MANIFEST" | sed '/^$/d' | LC_ALL=C sort -u > "$NORMALIZED_MANIFEST"

actual_archive_sha256="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
[[ "$actual_archive_sha256" == "$EXPECTED_ARCHIVE_SHA256" ]] || die "Source archive checksum mismatch"

log "Validating source archive"
python3 - "$ARCHIVE" "$NORMALIZED_MANIFEST" <<'PY'
import pathlib
import sys
import tarfile

archive_path, manifest_path = sys.argv[1:]
allowed_exact = {"docker-compose.yml"}
allowed_prefixes = (
    "BillNote_frontend/",
    "backend/",
    "nginx/",
    "deploy/compose/",
)
blocked_exact = {".env", "backend/bili_note.db"}
blocked_prefixes = (
    "backend/config/",
    "backend/data/",
    "backend/static/",
    "backend/uploads/",
    "backend/models/",
    "backend/logs/",
    "backend/bin/",
    "backend/note_results/",
    "deploy/audioread/",
)


def normalize(raw_path: str) -> str:
    if "\\" in raw_path:
        raise ValueError(f"backslash is not allowed in archive path: {raw_path}")
    while raw_path.startswith("./"):
        raw_path = raw_path[2:]
    normalized = pathlib.PurePosixPath(raw_path)
    if not raw_path or normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"unsafe archive path: {raw_path}")
    return normalized.as_posix()


def validate_managed(path: str) -> None:
    if path in blocked_exact or path.startswith(blocked_prefixes):
        raise ValueError(f"persistent path is blocked: {path}")
    if path not in allowed_exact and not path.startswith(allowed_prefixes):
        raise ValueError(f"unmanaged path is blocked: {path}")


manifest = []
for line in pathlib.Path(manifest_path).read_text(encoding="utf-8").splitlines():
    path = normalize(line)
    validate_managed(path)
    manifest.append(path)

if not manifest:
    raise ValueError("managed file manifest is empty")
if len(manifest) != len(set(manifest)):
    raise ValueError("managed file manifest contains duplicates")

archive_files = []
with tarfile.open(archive_path, "r:") as archive:
    for member in archive.getmembers():
        if member.isdir():
            continue
        if not member.isfile():
            raise ValueError(f"archive contains unsupported entry type: {member.name}")
        path = normalize(member.name)
        validate_managed(path)
        archive_files.append(path)

if len(archive_files) != len(manifest) or set(archive_files) != set(manifest):
    missing = sorted(set(manifest) - set(archive_files))[:10]
    extra = sorted(set(archive_files) - set(manifest))[:10]
    raise ValueError(f"archive/manifest mismatch; missing={missing}, extra={extra}")

print(f"validated_files={len(manifest)}")
PY

mkdir -p -- "$SOURCE_DIR"
tar -xf "$ARCHIVE" -C "$SOURCE_DIR" --no-same-owner
[[ -f "$SOURCE_DIR/docker-compose.yml" ]] || die "Snapshot is missing docker-compose.yml"
[[ -f "$SOURCE_DIR/deploy/compose/rn-direct-cliproxy.yml" ]] || die "Snapshot is missing the CLIProxyAPI Compose override"
[[ -f "$SOURCE_DIR/backend/Dockerfile" ]] || die "Snapshot is missing the backend Dockerfile"
[[ -f "$SOURCE_DIR/BillNote_frontend/Dockerfile" ]] || die "Snapshot is missing the frontend Dockerfile"

docker network inspect cli-proxy-api_default >/dev/null 2>&1 || die "Docker network cli-proxy-api_default does not exist"

env_hash_before="$(sha256sum "$REMOTE_DIR/.env" | awk '{print $1}')"
auth_hash_before="$(sha256sum "$REMOTE_DIR/deploy/audioread/.auth/qwen-audioread-auth.json" | awk '{print $1}')"
audioread_id_before="$(docker inspect --format '{{.Id}}' qwen-audioread-api)"

export BILINOTE_ENV_FILE="$REMOTE_DIR/.env"
compose_stage=(
    docker compose
    --project-name bilinote
    --project-directory "$SOURCE_DIR"
    --env-file "$REMOTE_DIR/.env"
    -f "$SOURCE_DIR/docker-compose.yml"
    -f "$SOURCE_DIR/deploy/compose/rn-direct-cliproxy.yml"
)

log "Checking Compose configuration"
"${compose_stage[@]}" config --quiet

log "Building backend image"
"${compose_stage[@]}" build backend

log "Building frontend image"
"${compose_stage[@]}" build frontend

log "Synchronizing managed source files"
mkdir -p -- "$STATE_DIR"
{
    if git -C "$REMOTE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git -C "$REMOTE_DIR" ls-files -- BillNote_frontend backend nginx docker-compose.yml deploy/compose
    fi
    if [[ -f "$PREVIOUS_MANIFEST" ]]; then
        cat "$PREVIOUS_MANIFEST"
    fi
} | tr -d '\r' | sed '/^$/d' | LC_ALL=C sort -u > "$CANDIDATES"
LC_ALL=C comm -23 "$CANDIDATES" "$NORMALIZED_MANIFEST" > "$STALE_FILES"

python3 - "$STALE_FILES" <<'PY'
import pathlib
import sys

allowed_exact = {"docker-compose.yml"}
allowed_prefixes = ("BillNote_frontend/", "backend/", "nginx/", "deploy/compose/")
blocked_exact = {".env", "backend/bili_note.db"}
blocked_prefixes = (
    "backend/config/",
    "backend/data/",
    "backend/static/",
    "backend/uploads/",
    "backend/models/",
    "backend/logs/",
    "backend/bin/",
    "backend/note_results/",
    "deploy/audioread/",
)

for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    path = pathlib.PurePosixPath(line)
    normalized = path.as_posix()
    if not line or path.is_absolute() or ".." in path.parts or "\\" in line:
        raise ValueError(f"unsafe stale path: {line}")
    if normalized in blocked_exact or normalized.startswith(blocked_prefixes):
        raise ValueError(f"persistent stale path is blocked: {normalized}")
    if normalized not in allowed_exact and not normalized.startswith(allowed_prefixes):
        raise ValueError(f"unmanaged stale path is blocked: {normalized}")
PY

tar -xf "$ARCHIVE" -C "$REMOTE_DIR" --no-same-owner
while IFS= read -r stale_path; do
    [[ -n "$stale_path" ]] || continue
    rm -f -- "$REMOTE_DIR/$stale_path"
done < "$STALE_FILES"
install -m 0644 "$NORMALIZED_MANIFEST" "$PREVIOUS_MANIFEST"

compose_live=(
    docker compose
    --project-name bilinote
    --project-directory "$REMOTE_DIR"
    --env-file "$REMOTE_DIR/.env"
    -f "$REMOTE_DIR/docker-compose.yml"
    -f "$REMOTE_DIR/deploy/compose/rn-direct-cliproxy.yml"
)

log "Recreating BiliNote services"
"${compose_live[@]}" up -d backend frontend nginx

log "Waiting for backend health"
backend_health=""
for _ in $(seq 1 60); do
    backend_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' bilinote-backend 2>/dev/null || true)"
    if [[ "$backend_health" == "healthy" ]]; then
        break
    fi
    sleep 2
done
[[ "$backend_health" == "healthy" ]] || die "BiliNote backend did not become healthy"
[[ "$(docker inspect --format '{{.State.Status}}' bilinote-frontend)" == "running" ]] || die "BiliNote frontend is not running"
[[ "$(docker inspect --format '{{.State.Status}}' bilinote-nginx)" == "running" ]] || die "BiliNote nginx is not running"

log "Running acceptance checks"
curl -fsS "http://127.0.0.1:11309/api/sys_check" >/dev/null
curl -fsS "http://127.0.0.1:11308/health" >/dev/null

audioread_id_after="$(docker inspect --format '{{.Id}}' qwen-audioread-api)"
[[ "$audioread_id_after" == "$audioread_id_before" ]] || die "AudioRead container was unexpectedly recreated"
[[ "$(sha256sum "$REMOTE_DIR/.env" | awk '{print $1}')" == "$env_hash_before" ]] || die ".env changed during deployment"
[[ "$(sha256sum "$REMOTE_DIR/deploy/audioread/.auth/qwen-audioread-auth.json" | awk '{print $1}')" == "$auth_hash_before" ]] || die "AudioRead authentication changed during deployment"
[[ -f "$REMOTE_DIR/backend/bili_note.db" ]] || die "Persistent database disappeared during deployment"

"${compose_live[@]}" exec -T backend python - <<'PY'
import json
import socket
import sqlite3
import urllib.request

resolved = socket.gethostbyname("cliproxyapi")
database = sqlite3.connect("/app/bili_note.db")
row = database.execute(
    "SELECT api_key FROM providers WHERE name = ? LIMIT 1",
    ("CLIProxyAPI",),
).fetchone()
if not row or not row[0]:
    raise RuntimeError("CLIProxyAPI provider key is missing")

request = urllib.request.Request(
    "http://cliproxyapi:8317/v1/models",
    headers={"Authorization": f"Bearer {row[0]}"},
)
with urllib.request.urlopen(request, timeout=10) as response:
    payload = json.load(response)

model_ids = {item.get("id") for item in payload.get("data", [])}
if "qmodel_latest" not in model_ids:
    raise RuntimeError("qmodel_latest is not available from CLIProxyAPI")
print(f"cliproxyapi={resolved} status=200 qmodel_latest=true")
PY

if [[ "$SKIP_PUBLIC_ACCESS_CHECK" == "0" ]]; then
    access_headers="$STAGE_DIR/cloudflare-access.headers"
    public_status="$(curl -sS -o /dev/null -D "$access_headers" -w '%{http_code}' "${PUBLIC_URL%/}/")"
    [[ "$public_status" == "302" ]] || die "Expected Cloudflare Access HTTP 302, got $public_status"
    grep -Eiq '^location: https://[^/]*cloudflareaccess\.com/' "$access_headers" || die "Cloudflare Access login redirect was not found"
fi

cat > "$STATE_DIR/last-deploy.txt" <<EOF
deployed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
local_head=$LOCAL_HEAD
archive_sha256=$EXPECTED_ARCHIVE_SHA256
public_url=$PUBLIC_URL
EOF
chmod 0644 "$STATE_DIR/last-deploy.txt"

"${compose_live[@]}" ps
printf '\nDeployment verification passed.\n'
DEPLOY_SUCCEEDED=1
