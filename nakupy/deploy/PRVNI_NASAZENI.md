# Nasazení na VPS

Server už provozuje `vydaje.dalcortile.cz`. Porty 80 a 443 tam drží **Caddy
v kontejneru** ze stacku `/opt/vydaje` a nasazuje se přes **GitHub Actions** —
z chatu se na server po SSH nedostane, klíč používá až runner GitHubu. Nákupy
jedou stejnou cestou, takže se nic nevymýšlí znovu.

```
push na GitHub → Actions (runner má SSH klíč v secretech)
               → scp archivu na VPS → deploy/deploy-nakupy.sh
               → /opt/nakupy: docker compose up
               → Caddy dostane další web a načte konfiguraci
```

Nákupy poslouchají na `127.0.0.1:8081` a zároveň jsou v docker síti Caddyho,
který je najde jako `nakupy:8000` a sám vyřídí HTTPS certifikát.

## Nejrychlejší cesta: terminál na serveru

Když se dá na server přihlásit přes SSH, nepotřebuje se nic dalšího —
ani GitHub Actions, ani žádné secrety:

```bash
curl -fsSL https://raw.githubusercontent.com/centycz/PLANEO_HLEDANI/BRANCH/nakupy/deploy/install-on-vps.sh -o /tmp/nakupy.sh
sudo bash /tmp/nakupy.sh
```

Skript stáhne aplikaci, založí `/opt/nakupy`, vygeneruje `.env` s náhodným
klíčem i heslem, sestaví a spustí kontejner a počká, až naběhne. Na konci
vypíše přihlašovací údaje. **Konfigurace Caddyho se přitom vůbec neotevře** —
aplikace zatím jede jen na `127.0.0.1:8081`.

Doména se přidá až zvlášť, když je jasné, že aplikace běží:

```bash
sudo bash /opt/nakupy/deploy/wire-caddy.sh            # přidá nakupy.dalcortile.cz
sudo bash /opt/nakupy/deploy/wire-caddy.sh --remove   # vrátí Caddyfile do původního stavu
```

Stejný skript slouží i pro pozdější aktualizace: pustí se znovu, data ani
`.env` nepřepíše a databázi před přepsáním souborů zazálohuje.

## Druhá cesta: GitHub Actions

## Co je potřeba jednou nastavit

1. **DNS** — `nakupy.dalcortile.cz` → IP serveru. (Hotovo.)
2. **Workflow s přístupem k serveru.** Přístupové údaje (`VPS_SSH_PRIVATE_KEY`,
   `VPS_SSH_KNOWN_HOSTS`) jsou v secretech repozitáře `centycz/spartito`.
   GitHub hodnoty secretů nikdy nevydá — nejde je zkopírovat jinam, ani je
   nemá k dispozici žádný chat. Workflow proto patří tam, kde ty klíče jsou:
   hotový soubor je v [`github/deploy-nakupy.yml`](github/deploy-nakupy.yml),
   stačí ho ve spartitu uložit jako `.github/workflows/deploy-nakupy.yml`.
   Druhá možnost: vygenerovat nový pár klíčů, veřejný přidat uživateli
   `deploy` do `~/.ssh/authorized_keys` a soukromý uložit jako secret
   v `PLANEO_HLEDANI` — to ale vyžaduje přístup na server.
3. **Volitelně secret `NAKUPY_ADMIN_PASSWORD`.** Bez něj skript při prvním
   spuštění vygeneruje náhodné heslo a vypíše ho do logu nasazení; po prvním
   přihlášení si ho změň v Nastavení.

## Spuštění

**Actions → Deploy nakupy → Run workflow**, napsat `DEPLOY` a vybrat větev.

Přepínač **„Přidat web do Caddyho"** rozhoduje, jestli se sáhne na stack
vydaje. Doporučený postup napoprvé:

1. **Zkušební běh s vypnutým přepínačem** — vznikne `/opt/nakupy`, aplikace
   naběhne na `127.0.0.1:8081`, konfigurace Caddyho se **vůbec neotevře**.
2. **Ostrý běh se zapnutým přepínačem** — teprve teď se přidá web pro doménu.

## Co dělá krok, který se dotýká vydaje

Je to jediné místo, kde nasazení nákupů sahá na cizí stack. Je vyčleněné do
samostatného skriptu [`wire-caddy.sh`](wire-caddy.sh), aby šlo spustit i vrátit
zvlášť, a je postavené tak, aby vydaje nemohly spadnout:

1. Zapíše se záloha `/opt/vydaje/Caddyfile.<datum>.bak`.
2. Nová konfigurace se složí do dočasného souboru a **ověří se v odhozeném
   kontejneru** (`caddy validate`) — běžícího Caddyho se to netýká.
3. Teprve po úspěšné kontrole se soubor vymění a zavolá se `caddy reload`,
   což je výměna konfigurace **bez výpadku**.
4. Kdyby reload přesto selhal, vrátí se původní soubor a načte se zpět.

Běžící Caddy se **nikdy nerestartuje** a stack vydaje se nepřestavuje.
Workflow navíc na konci ověří, že `vydaje.dalcortile.cz/api/health` pořád
odpovídá. Nejhorší možný výsledek je „nákupy nedostaly doménu", ne výpadek.

Přidaný blok v Caddyfile vypadá takhle a týká se výhradně nové domény:

```caddyfile
nakupy.dalcortile.cz {
  reverse_proxy nakupy:8000
}
```

Aby zůstal i po příštím nasazení vydaje (které `Caddyfile` přepíše z repozitáře),
je potřeba stejný blok doplnit i do `Caddyfile` v repozitáři spartito.

## Co se na serveru vytvoří

| Cesta | Obsah |
| --- | --- |
| `/opt/nakupy` | aplikace, `docker-compose.yml`, `.env` |
| `/opt/nakupy/data` | SQLite databáze a nahraná PDF |
| `/opt/nakupy/data/backup` | záloha databáze před každým nasazením (drží se 14) |

Kontejner se připojí do sítě, ve které běží Caddy — to je nutné, aby na něj
Caddy viděl. Znamená to, že je ve stejné docker síti jako ostatní kontejnery
vydaje; nákupy si k nim ale nikam nesahají a žádné přihlašovací údaje k nim
nemají.

## Ruční nasazení krok za krokem

```bash
ssh deploy@194.182.90.156
sudo mkdir -p /opt/nakupy && sudo chown deploy /opt/nakupy
git clone --branch claude/private-shopping-app-8bb7yj \
  https://github.com/centycz/PLANEO_HLEDANI.git /tmp/ph
cp -a /tmp/ph/nakupy/. /opt/nakupy/ && cd /opt/nakupy
cp .env.example .env
sed -i "s|^NAKUPY_SECRET_KEY=.*|NAKUPY_SECRET_KEY=$(openssl rand -hex 32)|" .env
nano .env                                    # nastav NAKUPY_ADMIN_PASSWORD
echo "NAKUPY_PROXY_NETWORK=vydaje_internal" >> .env
docker compose -f docker-compose.yml -f docker-compose.vps.yml up -d --build
curl -s http://127.0.0.1:8081/zdravi
```

Napojení na Caddy zvládne stejný skript, který používá i workflow — jde
spustit i vrátit samostatně:

```bash
bash /opt/nakupy/deploy/wire-caddy.sh            # přidá web pro doménu
bash /opt/nakupy/deploy/wire-caddy.sh --remove   # vrátí Caddyfile do původního stavu
```

## Zálohy

```bash
tar czf ~/nakupy-$(date +%F).tar.gz -C /opt/nakupy data
```

## Server bez Caddyho

Pro server, kde porty drží nginx, je připravená konfigurace v
[`nginx/nakupy.conf`](nginx/nakupy.conf) a systemd unit v
[`systemd/nakupy.service`](systemd/nakupy.service) pro běh bez Dockeru.
