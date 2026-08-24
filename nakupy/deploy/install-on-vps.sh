#!/usr/bin/env bash
# Instalace nákupní aplikace přímo na serveru - určeno k ručnímu spuštění
# z terminálu (klidně z mobilu). Dá se pouštět opakovaně: podruhé aplikaci
# jen aktualizuje, data ani .env nepřepíše.
#
#   curl -fsSL <adresa tohoto skriptu> -o /tmp/nakupy.sh
#   sudo bash /tmp/nakupy.sh
#
# Konfiguraci reverzní proxy (Caddy) tenhle skript zásadně NEMĚNÍ - na to je
# samostatný deploy/wire-caddy.sh, aby šlo nejdřív ověřit, že aplikace běží.
set -Eeuo pipefail

REPO="${NAKUPY_REPO:-https://github.com/centycz/PLANEO_HLEDANI.git}"
BRANCH="${NAKUPY_BRANCH:-claude/private-shopping-app-8bb7yj}"
PROJECT_DIR="${PROJECT_DIR:-/opt/nakupy}"
HOST_PORT="${NAKUPY_HOST_PORT:-8081}"

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
die() { printf '\n\033[31mChyba: %s\033[0m\n' "$1" >&2; exit 1; }

[[ "$(id -u)" == "0" ]] || die "Spusť skript přes sudo: sudo bash $0"
command -v docker >/dev/null || die "Docker na serveru není."
docker compose version >/dev/null 2>&1 || die "Chybí 'docker compose' (plugin v2)."
command -v git >/dev/null || die "Chybí git."
command -v openssl >/dev/null || die "Chybí openssl."

say "Stahuji aplikaci z větve ${BRANCH}"
checkout="$(mktemp -d /tmp/nakupy-src.XXXXXX)"
trap 'rm -rf -- "${checkout}"' EXIT
git clone --quiet --depth 1 --branch "${BRANCH}" "${REPO}" "${checkout}" \
  || die "Stažení se nepodařilo. Když je repozitář neveřejný, přihlas se ke gitu nebo použij NAKUPY_REPO s tokenem."
[[ -d "${checkout}/nakupy" ]] || die "Ve stažené větvi chybí adresář nakupy/."
revision="$(git -C "${checkout}" rev-parse --short HEAD)"

say "Připravuji ${PROJECT_DIR}"
mkdir -p "${PROJECT_DIR}/data"

first_run=0
if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
  first_run=1
  admin_password="${NAKUPY_ADMIN_PASSWORD:-$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-14)}"
  cat > "${PROJECT_DIR}/.env" <<ENVEOF
NAKUPY_SECRET_KEY=$(openssl rand -hex 32)
NAKUPY_DATA_DIR=/data
NAKUPY_ADMIN_USER=${NAKUPY_ADMIN_USER:-admin}
NAKUPY_ADMIN_PASSWORD=${admin_password}
NAKUPY_ADMIN_NAME=${NAKUPY_ADMIN_NAME:-Admin}
NAKUPY_SECURE_COOKIES=true
NAKUPY_TZ=Europe/Prague
NAKUPY_PORT=8000
NAKUPY_HOST_PORT=${HOST_PORT}
ENVEOF
  chmod 600 "${PROJECT_DIR}/.env"
fi

# záloha databáze před každou aktualizací
if [[ -f "${PROJECT_DIR}/data/nakupy.db" ]]; then
  say "Zálohuji databázi"
  mkdir -p "${PROJECT_DIR}/data/backup"
  cp "${PROJECT_DIR}/data/nakupy.db" \
     "${PROJECT_DIR}/data/backup/nakupy-$(date -u +%Y%m%dT%H%M%SZ).db"
  ls -1t "${PROJECT_DIR}/data/backup"/nakupy-*.db 2>/dev/null | tail -n +15 | xargs -r rm --
fi

# soubory aplikace se přepíšou, data a .env zůstávají
say "Kopíruji soubory aplikace"
rm -rf "${PROJECT_DIR}/app" "${PROJECT_DIR}/deploy" "${PROJECT_DIR}/tests"
cp -a "${checkout}/nakupy/." "${PROJECT_DIR}/"
rm -f "${PROJECT_DIR}/.env.example.bak"
printf '%s\n' "${revision}" > "${PROJECT_DIR}/.deploy-revision"

# --- síť reverzní proxy ---------------------------------------------------
# Aby na aplikaci viděl Caddy, který na serveru drží porty 80/443, musí být
# ve stejné docker síti. Když žádný Caddy neběží, jede aplikace jen lokálně.
compose_files=(-f docker-compose.yml)
proxy_network="$(
  caddy_name="$(docker ps --filter 'name=caddy' --format '{{.Names}}' | head -n1)"
  [[ -n "${caddy_name}" ]] && docker inspect "${caddy_name}" \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' 2>/dev/null \
    | tr ' ' '\n' | grep -v '^$' | head -n1
)" || true

cd "${PROJECT_DIR}"
if [[ -n "${proxy_network}" ]]; then
  say "Caddy běží v síti ${proxy_network}, připojuji se do ní"
  if grep -q '^NAKUPY_PROXY_NETWORK=' .env; then
    sed -i "s|^NAKUPY_PROXY_NETWORK=.*|NAKUPY_PROXY_NETWORK=${proxy_network}|" .env
  else
    echo "NAKUPY_PROXY_NETWORK=${proxy_network}" >> .env
  fi
  compose_files+=(-f docker-compose.vps.yml)
else
  say "Žádný Caddy neběží - aplikace pojede jen na 127.0.0.1:${HOST_PORT}"
fi

say "Sestavuji a spouštím kontejner (chvíli to potrvá)"
docker compose "${compose_files[@]}" config --quiet
docker compose "${compose_files[@]}" up -d --build --remove-orphans

say "Čekám, až aplikace naběhne"
health='starting'
for _ in $(seq 1 45); do
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' nakupy 2>/dev/null || true)"
  [[ "${health}" == 'healthy' ]] && break
  sleep 2
done
if [[ "${health}" != 'healthy' ]]; then
  docker compose "${compose_files[@]}" logs --tail=120
  die "Aplikace nenaskočila (stav: ${health}). Výpis je nahoře."
fi

curl --fail --silent --show-error "http://127.0.0.1:${HOST_PORT}/zdravi" && echo

cat <<SUMMARY

========================================================================
 Nákupy běží: http://127.0.0.1:${HOST_PORT}   (verze ${revision})
SUMMARY
if [[ "${first_run}" == "1" ]]; then
  cat <<SUMMARY
 Přihlášení:  $(grep '^NAKUPY_ADMIN_USER=' .env | cut -d= -f2-)  /  $(grep '^NAKUPY_ADMIN_PASSWORD=' .env | cut -d= -f2-)
 Heslo si po prvním přihlášení změň v Nastavení.
SUMMARY
fi
cat <<SUMMARY

 Zatím to jede jen lokálně - na stack vydaje se nesáhlo.
 Doménu nakupy.dalcortile.cz přidáš tímhle:

     sudo bash ${PROJECT_DIR}/deploy/wire-caddy.sh

 A kdyby cokoli, vrátí se to zpátky:

     sudo bash ${PROJECT_DIR}/deploy/wire-caddy.sh --remove
========================================================================
SUMMARY
