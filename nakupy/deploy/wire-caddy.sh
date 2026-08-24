#!/usr/bin/env bash
# Přidá Caddymu, který na serveru drží porty 80/443, web pro nákupy.
#
# Tohle je jediné místo, kde nasazení nákupů sahá na cizí stack (/opt/vydaje),
# proto je celé postavené na jistotu:
#   1. záloha původního Caddyfile
#   2. nová konfigurace se ověří v odhozeném kontejneru (běžícího Caddyho se
#      to netýká)
#   3. teprve po úspěšné kontrole se soubor vymění a zavolá se `caddy reload`,
#      což je výměna konfigurace bez výpadku
#   4. kdyby reload selhal, vrátí se původní soubor a načte se zpět
#
# Běžící Caddy se nikdy nerestartuje. Nejhorší možný výsledek je "nákupy
# nedostaly doménu", ne výpadek vydaje.
#
# Použití:      bash deploy/wire-caddy.sh
# Odebrání:     bash deploy/wire-caddy.sh --remove
set -Eeuo pipefail

domain="${NAKUPY_DOMAIN:-nakupy.dalcortile.cz}"
caddyfile="${CADDYFILE:-/opt/vydaje/Caddyfile}"
upstream="${NAKUPY_UPSTREAM:-nakupy:8000}"
action="${1:-add}"

if [[ ! -f "${caddyfile}" ]]; then
  echo "Caddyfile ${caddyfile} neexistuje - není co upravovat." >&2
  exit 1
fi

caddy_container="$(docker ps --filter 'name=caddy' --format '{{.Names}}' | head -n1)"
if [[ -z "${caddy_container}" ]]; then
  echo 'Caddy neběží - web se nepřidává.' >&2
  exit 1
fi
caddy_image="$(docker inspect --format '{{.Config.Image}}' "${caddy_container}")"

candidate="$(mktemp /tmp/nakupy-caddyfile.XXXXXX)"
cleanup() { rm -f -- "${candidate}"; }
trap cleanup EXIT

if [[ "${action}" == "--remove" ]]; then
  if ! grep -q "${domain}" "${caddyfile}"; then
    echo "${domain} v konfiguraci není, nic se nemění."
    exit 0
  fi
  # smaže blok od řádku s doménou po jeho uzavírací závorku v prvním sloupci
  awk -v domain="${domain}" '
    index($0, domain) && /\{[[:space:]]*$/ { skip = 1; next }
    skip && /^\}/ { skip = 0; next }
    !skip { print }
  ' "${caddyfile}" > "${candidate}"
  # blok se přidával za prázdný řádek - srovnáme konec souboru zpět
  printf '%s\n' "$(cat "${candidate}")" > "${candidate}.trim"
  mv "${candidate}.trim" "${candidate}"
else
  if grep -q "${domain}" "${caddyfile}"; then
    echo "${domain} už v konfiguraci je, nic se nemění."
    exit 0
  fi
  cat "${caddyfile}" > "${candidate}"
  cat >> "${candidate}" <<CADDYEOF

${domain} {
  encode zstd gzip
  header {
    Strict-Transport-Security "max-age=31536000; includeSubDomains"
    X-Content-Type-Options "nosniff"
    Referrer-Policy "strict-origin-when-cross-origin"
    X-Frame-Options "DENY"
    -Server
  }
  request_body {
    max_size 60MB
  }
  reverse_proxy ${upstream}
  log {
    output stdout
    format json
  }
}
CADDYEOF
fi

backup="${caddyfile}.$(date -u +%Y%m%dT%H%M%SZ).bak"
cp "${caddyfile}" "${backup}"
echo "Záloha původní konfigurace: ${backup}"

# ověření mimo běžící Caddy
if ! docker run --rm -v "${candidate}:/etc/caddy/Caddyfile:ro" "${caddy_image}" \
     caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile; then
  echo 'Nová konfigurace neprošla kontrolou - na serveru se nic nezměnilo.' >&2
  exit 1
fi

cat "${candidate}" > "${caddyfile}"

if docker exec "${caddy_container}" \
     caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; then
  echo "Caddy načetl konfiguraci (${action} ${domain})."
else
  echo 'Načtení selhalo - vracím původní konfiguraci.' >&2
  cat "${backup}" > "${caddyfile}"
  docker exec "${caddy_container}" \
    caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile || true
  echo 'Původní konfigurace obnovena, vydaje běží dál.' >&2
  exit 1
fi
