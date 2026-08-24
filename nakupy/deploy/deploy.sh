#!/usr/bin/env bash
# Nasazeni / aktualizace aplikace na VPS.
#
#   ssh vps
#   cd /srv/nakupy/PLANEO_HLEDANI/nakupy
#   ./deploy/deploy.sh
#
# Skript stahne posledni verzi z gitu, prestavi image a restartuje kontejner.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRANCH="${NAKUPY_BRANCH:-claude/private-shopping-app-8bb7yj}"
HEALTH_URL="http://127.0.0.1:${NAKUPY_HOST_PORT:-8081}/zdravi"

cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "Chybi soubor .env - zkopiruj .env.example a vypln hodnoty." >&2
  exit 1
fi

echo "==> Stahuji zmeny z vetve $BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "==> Zaloha databaze"
if [ -f data/nakupy.db ]; then
  mkdir -p data/backup
  cp data/nakupy.db "data/backup/nakupy-$(date +%Y%m%d-%H%M%S).db"
  # drzime poslednich 14 zaloh
  ls -1t data/backup/nakupy-*.db | tail -n +15 | xargs -r rm --
fi

echo "==> Sestavuji a spoustim kontejner"
docker compose up -d --build

echo "==> Cekam na health check"
for attempt in $(seq 1 30); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "==> Hotovo: $(curl -fsS "$HEALTH_URL")"
    exit 0
  fi
  sleep 2
done

echo "Aplikace nenaskocila, podivej se do logu: docker compose logs --tail=100" >&2
exit 1
