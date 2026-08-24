# První nasazení na VPS

Postup je stejný jako u `vydaje.dalcortile.cz`, jen se změní subdoména a port.
Aplikace poslouchá na `127.0.0.1:8081`, ven ji pouští nginx na hostiteli — takže
si nijak nekoliduje s tím, co na serveru běží teď.

## 1. DNS

U domény `dalcortile.cz` přidej `A` záznam:

```
nakupy.dalcortile.cz.   A   <IP adresa VPS>
```

## 2. Kód na server

```bash
ssh root@<vps>
mkdir -p /srv/nakupy && cd /srv/nakupy
git clone https://github.com/centycz/PLANEO_HLEDANI.git
cd PLANEO_HLEDANI
git checkout claude/private-shopping-app-8bb7yj
cd nakupy
```

## 3. Konfigurace

```bash
cp .env.example .env
# vygeneruj tajný klíč pro session cookie
sed -i "s|^NAKUPY_SECRET_KEY=.*|NAKUPY_SECRET_KEY=$(openssl rand -hex 32)|" .env
nano .env      # nastav NAKUPY_ADMIN_USER a NAKUPY_ADMIN_PASSWORD
```

Heslo z `.env` se použije jen při úplně prvním startu, kdy se zakládá první
účet. Potom se mění v aplikaci v Nastavení.

## 4. Start

```bash
docker compose up -d --build
curl http://127.0.0.1:8081/zdravi     # {"status":"ok","version":"1.0.0"}
```

## 5. nginx + HTTPS

```bash
cp deploy/nginx/nakupy.conf /etc/nginx/sites-available/nakupy.dalcortile.cz
ln -s /etc/nginx/sites-available/nakupy.dalcortile.cz /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d nakupy.dalcortile.cz
```

Hotovo — aplikace běží na <https://nakupy.dalcortile.cz>.

## 6. Další aktualizace

```bash
cd /srv/nakupy/PLANEO_HLEDANI/nakupy
./deploy/deploy.sh
```

Skript stáhne novou verzi z GitHubu, zazálohuje databázi, přestaví image
a počká, až aplikace naběhne.

## Zálohy

Data (SQLite databáze + nahraná PDF) jsou v adresáři `nakupy/data`. Záloha:

```bash
tar czf /root/nakupy-$(date +%F).tar.gz -C /srv/nakupy/PLANEO_HLEDANI/nakupy data
```

`deploy/deploy.sh` navíc před každou aktualizací odloží kopii databáze do
`data/backup/` a drží posledních 14 kusů.

## Varianta bez Dockeru

Když nechceš Docker, použij `deploy/systemd/nakupy.service`:

```bash
adduser --system --group nakupy
mkdir -p /srv/nakupy/{app,data}
python3 -m venv /srv/nakupy/venv
/srv/nakupy/venv/bin/pip install -r requirements.txt
cp -r app /srv/nakupy/app/
cp .env /srv/nakupy/.env
chown -R nakupy:nakupy /srv/nakupy
cp deploy/systemd/nakupy.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now nakupy
```
