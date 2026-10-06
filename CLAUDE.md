# Influenszer Radar – fejlesztői jegyzet

Helyi európai influenszer-kereső: helyszín + km-sugár → igény szerinti gyűjtés csak arra a körzetre → demográfiai / pszichográfiai / célközönség-szűrés, HU/EN. Felhasználói leírás (források, szűrők, importformátum, CLI): README.md.

## Indítás és teszt
- `./run.sh` → http://127.0.0.1:8790 (venv-et csinál `/opt/homebrew/bin/python3.14`-gyel, ha nincs, betölti a `.env`-et). CLI: `.venv/bin/python -m influradar collect|import|enrich|search|stats|clear` (példák a README-ben).
- launch.json: `radar-gui` (`~/Claude_code/.claude/launch.json`) → 127.0.0.1:8799 (`--port 8799`, hogy ne ütközzön a 8790-es alapértékkel).
- Adat: repóból futtatva `./data/` (`radar.sqlite`, `cache/`), csomagolt appban a felhasználói mappa (`influradar/paths.py`); `INFLURADAR_DATA` felülírja, `INFLURADAR_USERDIR=1` a felhasználói mappát kényszeríti.
- Automatikus teszt nincs. Kézi füstteszt: GUI-ban egy kis körzet (pl. Graz, 20 km, 2 város) DDG-gyűjtése – de takarékosan, lásd Buktatók.

## Felépítés
- `influradar/geo.py` – Nominatim keresés/reverse (1 kérés/mp), Overpass `towns_within` mirrorokkal + lemez-cache a `data/cache`-ben, magyar CSV-tartalék (`data/telepulesek.csv`).
- `influradar/discover.py` – webkeresés-felderítés `site:` lekérdezésekkel az ország nyelvén + angolul (`TERMS`, 30+ nyelv); Brave Search API, ha van `BRAVE_SEARCH_API_KEY`, különben DuckDuckGo (`ddgs`).
- `influradar/db.py` – SQLite, normalizálás, `search()` szűrőmotor facetekkel (ország/megye chipek). A `collections` tábla köti a profilokat a körzethez (`collection_id`); a UI a legutóbbi kész gyűjtést nyitja meg.
- `influradar/taxonomy.py` – szótárak + célcsoport-előbeállítások (HU/EN tuple-ök). `contacts.py` – elérhetőség-kiegészítés. `modash.py` – fizetős API-adapter (`MODASH_API_KEY`).
- `influradar/llm.py` – dúsítás, háttérlánc: API-kulcs → Claude Code CLI → Ollama → szabályalapú. `paths.py` – erőforrás- és adatmappa, `.env` betöltés (adatmappa, repo gyökér, cwd).
- `influradar/webapp.py` + `ui.html` – stdlib HTTP API és egyoldalas Leaflet-felület.

## Telepítés / kiadás
- Verzió: `influradar/__init__.py` `__version__` (jelenleg 0.2.2). Kiadás: /release skill; `v*` tag push → `.github/workflows/release.yml` PyInstaller-appokat épít (macOS arm64 + x86_64, Windows x64, Linux x86_64) és release-hez csatolja.
- Helyi build: `./build_app.sh` → `dist/`. Docker: `Dockerfile` (port 8790, `/data` kötet).

## Döntések
1. Igény szerinti gyűjtés csak a választott körzetre, nem egész ország előre (a tulajdonos kérése).
2. Nincs scraping: nincs ingyenes hivatalos influenszer-API, a platformok scrapelése ToS- és GDPR-kockázat. Források: keresőmotoros felderítés, CSV/JSON import fizetős szolgáltatóktól, Modash-adapter, kézi felvitel. Scraping csak kifejezett jogi jóváhagyás esetén jöhet szóba.
3. Demo/szintetikus adat teljesen eltávolítva (2026-09-19, a tulajdonos kérése) – ne kerüljön vissza.
4. Ha a keresőmotor bot-védelme blokkol, a gyűjtés `blocked` státusszal leáll HU/EN magyarázattal. CAPTCHA-kerülés nincs és nem is lesz.
5. Csak 127.0.0.1-en fut; ugyanaz a felépítés, mint az osint-dd-ben (stdlib http.server, SQLite, LLM-lánc, „crafted by sadrobot”).

## Buktatók
- A kulcs nélküli keresők (DDG/Bing/Brave web) néhány gyűjtés után órákra letilthatják az IP-t – 2026-09-19-én ez meg is történt. Ezért kevés, kis gyűjtéssel tesztelj, vagy Brave API-kulccsal.
- A Modash-adapter mezőleképezése best-effort, éles kulccsal még nem tesztelt.

## Nyitott
- Modash éles teszt.
