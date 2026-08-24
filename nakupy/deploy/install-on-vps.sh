#!/usr/bin/env bash
# Instalace nákupní aplikace přímo na serveru.
#
# Dá se spustit dvěma způsoby:
#   * ručně z terminálu:   sudo bash /tmp/nakupy.sh
#   * bez přihlášení k serveru, přes GitHub Actions, které skript pošlou
#     po SSH:              curl -fsSL <adresa> | ssh deploy@server bash -s
#
# Root není potřeba: když skript běží pod běžným uživatelem bez sudo,
# nainstaluje se do ~/nakupy místo /opt/nakupy.
#
# Opakované spuštění aplikaci jen aktualizuje - data ani .env nepřepíše.
# Konfiguraci reverzní proxy (Caddy) tenhle skript zásadně NEMĚNÍ, na to je
# samostatný deploy/wire-caddy.sh.
set -Eeuo pipefail

REPO_URL="${NAKUPY_REPO:-https://github.com/centycz/PLANEO_HLEDANI}"
BRANCH="${NAKUPY_BRANCH:-claude/private-shopping-app-8bb7yj}"
HOST_PORT="${NAKUPY_HOST_PORT:-8081}"

say() { printf '\n==> %s\n' "$1"; }
die() { printf '\nChyba: %s\n' "$1" >&2; exit 1; }

# --- práva: root, sudo bez hesla, nebo ani jedno --------------------------
SUDO=""
if [[ "$(id -u)" != "0" ]] && sudo -n true 2>/dev/null; then
  SUDO="sudo"
fi

if [[ -z "${PROJECT_DIR:-}" ]]; then
  if [[ "$(id -u)" == "0" || -n "${SUDO}" || -w /opt ]]; then
    PROJECT_DIR=/opt/nakupy
  else
    PROJECT_DIR="${HOME}/nakupy"
    say "Bez práv roota - instaluji do ${PROJECT_DIR}"
  fi
fi

command -v docker >/dev/null || die "Docker na serveru není."
# docker může vyžadovat sudo, když uživatel není ve skupině docker
if ! docker info >/dev/null 2>&1; then
  [[ -n "${SUDO}" ]] || die "Na docker chybí práva. Spusť skript přes sudo."
  DOCKER=(${SUDO} docker)
else
  DOCKER=(docker)
fi
"${DOCKER[@]}" compose version >/dev/null 2>&1 || die "Chybí 'docker compose' (plugin v2)."
command -v openssl >/dev/null || die "Chybí openssl."

# --- stažení aplikace -----------------------------------------------------
say "Stahuji aplikaci z větve ${BRANCH}"
checkout="$(mktemp -d /tmp/nakupy-src.XXXXXX)"
trap 'rm -rf -- "${checkout}"' EXIT

if command -v git >/dev/null; then
  git clone --quiet --depth 1 --branch "${BRANCH}" "${REPO_URL}.git" "${checkout}" \
    || die "Stažení se nepodařilo. Když je repozitář neveřejný, použij NAKUPY_REPO s tokenem."
  revision="$(git -C "${checkout}" rev-parse --short HEAD)"
else
  # bez gitu stáhneme archiv větve
  slug="${REPO_URL#https://github.com/}"
  curl -fsSL "https://codeload.github.com/${slug}/tar.gz/refs/heads/${BRANCH}" \
    | tar xz -C "${checkout}" --strip-components=1 \
    || die "Stažení archivu se nepodařilo."
  revision="${BRANCH}"
fi
[[ -d "${checkout}/nakupy" ]] || die "Ve stažené větvi chybí adresář nakupy/."

# --- adresář projektu -----------------------------------------------------
say "Připravuji ${PROJECT_DIR}"
if [[ ! -d "${PROJECT_DIR}" ]]; then
  ${SUDO} mkdir -p "${PROJECT_DIR}" || die "Nepodařilo se vytvořit ${PROJECT_DIR}."
  [[ -n "${SUDO}" ]] && ${SUDO} chown "$(id -u):$(id -g)" "${PROJECT_DIR}"
fi
[[ -w "${PROJECT_DIR}" ]] || die "Do ${PROJECT_DIR} se nedá zapisovat. Spusť skript přes sudo."
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

if [[ -f "${PROJECT_DIR}/data/nakupy.db" ]]; then
  say "Zálohuji databázi"
  mkdir -p "${PROJECT_DIR}/data/backup"
  cp "${PROJECT_DIR}/data/nakupy.db" \
     "${PROJECT_DIR}/data/backup/nakupy-$(date -u +%Y%m%dT%H%M%SZ).db"
  ls -1t "${PROJECT_DIR}/data/backup"/nakupy-*.db 2>/dev/null | tail -n +15 | xargs -r rm --
fi

say "Kopíruji soubory aplikace"
rm -rf "${PROJECT_DIR}/app" "${PROJECT_DIR}/deploy" "${PROJECT_DIR}/tests"
cp -a "${checkout}/nakupy/." "${PROJECT_DIR}/"
printf '%s\n' "${revision}" > "${PROJECT_DIR}/.deploy-revision"

# --- síť reverzní proxy ---------------------------------------------------
# Aby na aplikaci viděl Caddy, který drží porty 80/443, musí být ve stejné
# docker síti. Když žádný Caddy neběží, jede aplikace jen lokálně.
compose_files=(-f docker-compose.yml)
caddy_name="$("${DOCKER[@]}" ps --filter 'name=caddy' --format '{{.Names}}' 2>/dev/null | head -n1 || true)"
proxy_network=""
if [[ -n "${caddy_name}" ]]; then
  proxy_network="$("${DOCKER[@]}" inspect "${caddy_name}" \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}' 2>/dev/null \
    | tr ' ' '\n' | grep -v '^$' | head -n1 || true)"
fi

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
"${DOCKER[@]}" compose "${compose_files[@]}" config --quiet
"${DOCKER[@]}" compose "${compose_files[@]}" up -d --build --remove-orphans

say "Čekám, až aplikace naběhne"
health='starting'
for _ in $(seq 1 45); do
  health="$("${DOCKER[@]}" inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' nakupy 2>/dev/null || true)"
  [[ "${health}" == 'healthy' ]] && break
  sleep 2
done
if [[ "${health}" != 'healthy' ]]; then
  "${DOCKER[@]}" compose "${compose_files[@]}" logs --tail=120
  die "Aplikace nenaskočila (stav: ${health}). Výpis je nahoře."
fi

curl --fail --silent --show-error "http://127.0.0.1:${HOST_PORT}/zdravi" && echo

echo
echo "========================================================================"
echo " Nákupy běží: http://127.0.0.1:${HOST_PORT}   (verze ${revision})"
if [[ "${first_run}" == "1" ]]; then
  echo " Přihlášení:  $(grep '^NAKUPY_ADMIN_USER=' .env | cut -d= -f2-)  /  $(grep '^NAKUPY_ADMIN_PASSWORD=' .env | cut -d= -f2-)"
  echo " Heslo si po prvním přihlášení změň v Nastavení."
fi
echo
echo " Na stack vydaje se zatím nesáhlo. Doménu přidá:"
echo "     bash ${PROJECT_DIR}/deploy/wire-caddy.sh"
echo " a vrátí zpět:"
echo "     bash ${PROJECT_DIR}/deploy/wire-caddy.sh --remove"
echo "========================================================================"
