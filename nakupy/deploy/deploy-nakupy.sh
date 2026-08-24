#!/usr/bin/env bash
# Beží na VPS - přijímá se přes `ssh ... bash -s < deploy/deploy-nakupy.sh`.
# Rozbalí nahraný archiv do /opt/nakupy, spustí kontejner a napojí ho na Caddy.
set -Eeuo pipefail

project_dir="${PROJECT_DIR:-/opt/nakupy}"
archive="${DEPLOY_ARCHIVE:?DEPLOY_ARCHIVE je povinný}"
expected_checksum="${DEPLOY_ARCHIVE_SHA256:?DEPLOY_ARCHIVE_SHA256 je povinný}"
deploy_sha="${DEPLOY_SHA:?DEPLOY_SHA je povinný}"
domain="${NAKUPY_DOMAIN:-nakupy.dalcortile.cz}"
caddyfile="${CADDYFILE:-/opt/vydaje/Caddyfile}"

case "${deploy_sha}" in
  *[!0-9a-f]* | '') echo 'DEPLOY_SHA musí být hexadecimální commit.' >&2; exit 1 ;;
esac

resolved_project_dir="$(readlink -f "${project_dir}")"
if [[ "${resolved_project_dir}" != '/opt/nakupy' ]]; then
  echo "Odmítám nasazovat mimo /opt/nakupy: ${resolved_project_dir}" >&2
  exit 1
fi
if [[ ! -f "${archive}" ]]; then
  echo 'Nahraný archiv chybí.' >&2
  exit 1
fi
actual_checksum="$(sha256sum "${archive}" | cut -d' ' -f1)"
if [[ "${actual_checksum}" != "${expected_checksum}" ]]; then
  echo 'Kontrolní součet archivu nesouhlasí.' >&2
  exit 1
fi

stage_dir="$(mktemp -d /tmp/nakupy-deploy-stage.XXXXXX)"
cleanup() { rm -rf -- "${stage_dir}" "${archive}"; }
trap cleanup EXIT

tar -xf "${archive}" -C "${stage_dir}"
if [[ -e "${stage_dir}/.env" ]]; then
  echo 'Archiv nikdy nesmí obsahovat .env.' >&2
  exit 1
fi
if [[ ! -f "${stage_dir}/docker-compose.yml" || ! -f "${stage_dir}/Dockerfile" ]]; then
  echo 'Archiv není kompletní vydání aplikace.' >&2
  exit 1
fi

mkdir -p "${project_dir}/data"

# --- první spuštění: vlastní .env s náhodnými hesly -----------------------
if [[ ! -f "${project_dir}/.env" ]]; then
  admin_password="${NAKUPY_ADMIN_PASSWORD:-$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-12)}"
  cat > "${project_dir}/.env" <<ENVEOF
NAKUPY_SECRET_KEY=$(openssl rand -hex 32)
NAKUPY_DATA_DIR=/data
NAKUPY_ADMIN_USER=${NAKUPY_ADMIN_USER:-admin}
NAKUPY_ADMIN_PASSWORD=${admin_password}
NAKUPY_ADMIN_NAME=${NAKUPY_ADMIN_NAME:-Admin}
NAKUPY_SECURE_COOKIES=true
NAKUPY_TZ=Europe/Prague
NAKUPY_PORT=8000
NAKUPY_HOST_PORT=8081
ENVEOF
  chmod 600 "${project_dir}/.env"
  echo "PRVNÍ SPUŠTĚNÍ: přihlašovací jméno '${NAKUPY_ADMIN_USER:-admin}', heslo '${admin_password}'"
  echo "Heslo si po přihlášení změň v Nastavení; je uložené v ${project_dir}/.env."
fi

# --- záloha databáze před přepsáním souborů -------------------------------
if [[ -f "${project_dir}/data/nakupy.db" ]]; then
  mkdir -p "${project_dir}/data/backup"
  cp "${project_dir}/data/nakupy.db" \
     "${project_dir}/data/backup/nakupy-$(date -u +%Y%m%dT%H%M%SZ).db"
  ls -1t "${project_dir}/data/backup"/nakupy-*.db | tail -n +15 | xargs -r rm --
fi

# aplikace se přepíše, data a .env zůstávají
rsync -a --delete --exclude '.env' --exclude 'data/' "${stage_dir}/" "${project_dir}/" 2>/dev/null \
  || cp -a "${stage_dir}/." "${project_dir}/"

cd "${project_dir}"

# --- síť, ve které běží Caddy z vydaje ------------------------------------
proxy_network="$(
  docker inspect "$(docker ps --filter 'name=caddy' --format '{{.Names}}' | head -n1)" \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' 2>/dev/null \
    | tr ' ' '\n' | grep -v '^$' | head -n1 || true
)"
proxy_network="${proxy_network:-vydaje_internal}"
echo "Caddy běží v síti: ${proxy_network}"
grep -q '^NAKUPY_PROXY_NETWORK=' .env \
  && sed -i "s|^NAKUPY_PROXY_NETWORK=.*|NAKUPY_PROXY_NETWORK=${proxy_network}|" .env \
  || echo "NAKUPY_PROXY_NETWORK=${proxy_network}" >> .env

docker compose -f docker-compose.yml -f docker-compose.vps.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.vps.yml build
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --remove-orphans

# --- health check ---------------------------------------------------------
health='starting'
for _ in $(seq 1 45); do
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' nakupy 2>/dev/null || true)"
  [[ "${health}" == 'healthy' ]] && break
  sleep 2
done
if [[ "${health}" != 'healthy' ]]; then
  docker compose -f docker-compose.yml -f docker-compose.vps.yml logs --tail=120 >&2
  echo "Aplikace nenaskočila (stav: ${health})." >&2
  exit 1
fi

# --- Caddy: doplnit web pro nakupy ---------------------------------------
# Samotná úprava je v deploy/wire-caddy.sh, aby šla spustit i vrátit zvlášť.
if [[ "${NAKUPY_WIRE_PROXY:-1}" == "1" ]]; then
  NAKUPY_DOMAIN="${domain}" CADDYFILE="${caddyfile}" \
    bash "${project_dir}/deploy/wire-caddy.sh"
else
  echo "Napojení na Caddy přeskočeno (NAKUPY_WIRE_PROXY=0)."
  echo "Aplikace běží na http://127.0.0.1:${NAKUPY_HOST_PORT:-8081}; stacku vydaje se nasazení nedotklo."
fi

printf '%s\n' "${deploy_sha}" > "${project_dir}/.deploy-revision"
docker compose -f docker-compose.yml -f docker-compose.vps.yml ps
curl --fail --silent --show-error "http://127.0.0.1:${NAKUPY_HOST_PORT:-8081}/zdravi"
printf '\nNasazeno %s.\n' "${deploy_sha}"
