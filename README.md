# Influenszer Radar / Influencer Radar · *crafted by sadrobot*

Helyi, a saját gépeden futó **európai influenszer-kereső**. A folyamat: **1. helyszín** (bármely európai város, autocomplete) + km-sugár → **2. gyűjtés** csak erre a körzetre (a sugáron belüli városokra, az ország nyelvén és angolul) → **3. szűrés** demográfiai, pszichográfiai és célközönség-szűrőkkel, lista, CSV. Nem tölt előre egész országot; a gyűjtések megmaradnak és újra megnyithatók. Térkép, HU/EN felület, SQLite, napló.

*Local, on-device **European influencer finder**: 1. pick any European place + radius → 2. collect only for that area (towns within the radius, country language + English) → 3. filter by demographics, psychographics and audience, save lists, export CSV. Nothing is preloaded per country; collections persist and can be reopened. Map, HU/EN UI, SQLite, audit log.*

## Futtatás / Running

| Mód | Hogyan | Kell hozzá |
|---|---|---|
| **Kész app (ajánlott más gépre)** | [Releases](https://github.com/krisztianhari-wq/influenszer-radar/releases): zip kicsomagolás → dupla klikk az `InfluenszerRadar` fájlra → elindul a helyi szerver és megnyílik a böngésző. macOS: első indításnál jobb klikk → Megnyitás; Windows: SmartScreen „További információ → Futtatás mindenképp”. | semmi (Python sem) |
| **Forrásból** | `git clone … && ./run.sh` → http://127.0.0.1:8790 | Python 3.10+ |
| **Docker** | `docker build -t influenszer-radar . && docker run -p 8790:8790 -v radar-data:/data influenszer-radar` | Docker |
| **Saját build** | `pip install -r requirements.txt pyinstaller && ./build_app.sh` → `dist/` | Python 3.10+ |

A kész app az adatokat a felhasználói mappában tartja (macOS `~/Library/Application Support/InfluenszerRadar`, Windows `%APPDATA%\InfluenszerRadar`, Linux `~/.local/share/InfluenszerRadar`); az `INFLURADAR_DATA` környezeti változó átirányítja. A GitHub Actions minden `v*` címkére felépíti a macOS (Apple Silicon + Intel), Windows és Linux csomagot.

*Ready-made app from Releases (no Python needed), or `./run.sh` from source, or Docker. Data lives in the user profile folder; `INFLURADAR_DATA` overrides it.*

## Szűrők

| Csoport | Szűrők |
|---|---|
| **Hely** | bármely európai település (OpenStreetMap Nominatim autocomplete; 149 magyar város offline is), **sugár 5–250 km** (Haversine); a körben lévő városokat az OSM Overpass adja népesség szerint; ország és megye/körzet chipek a gyűjtött adatból (facet) |
| **Gyűjtés** | források pipálhatók: DuckDuckGo (valós jelöltek), Demo (szintetikus, a körzet városaira), Modash (kulccsal); max. város a körben, extra kulcsszavak, automatikus LLM-címkézés; leállítható; korábbi gyűjtések listája |
| **Célcsoport-előbeállítás** | egy kattintás több szűrőt állít be: Z generáció, fiatal felnőttek, kisgyerekes családok, egyetemisták, sportos/egészségtudatos, gamerek/tech, nők 25–44, prémium, árérzékeny, KKV/vállalkozók, early adopterek, lokálpatrióta, zöld, aktív 45+ (`taxonomy.TARGET_GROUPS`, bővíthető) |
| **Alap** | platform (IG/TikTok/YT/FB/X/LinkedIn/Twitch), méret (nano/micro/mid/macro/mega), követő min/max, engagement % min, szabad szó |
| **Influenszer demográfia** | nem, kor min/max, nyelv |
| **Pszichográfia** | tartalmi kategória (22), érdeklődés (20), értékek (15), életstílus (15), hangnem (10); „bármelyik” vagy „mind kell” illesztés |
| **Célközönség** | közönség korcsoport + min. arány %, közönség nem + min. arány %, közönség lakhelye (település) + min. arány %, közönség érdeklődése |

Rendezés: követő, ER, távolság, név. Export: CSV (Excel-kompatibilis, UTF-8 BOM). Mentett listák: szűrőkkel együtt, CSV-ben is letölthetők.

## Adatforrások – mi ingyenes, mi nem

Influenszer-adatra **nincs ingyenes hivatalos API**, a platformok scrapelése pedig ToS-sértő és GDPR-kockázat, ezért **nincs beépítve**. Ami van:

| Forrás | Mit ad | Költség |
|---|---|---|
| **Demo** | szintetikus, `*_demo` handle-ű profilok a kiválasztott körzet városaira, teljes pszichográfiával és közönségeloszlással – a szűrők kipróbálására bárhol Európában. Nem valós személyek. | – |
| **DuckDuckGo felderítés** | a körzet városaira `site:instagram.com "Graz" influencer` típusú keresések **az ország nyelvén + angolul** (30+ nyelv szótára a `discover.py`-ban, DDG-régiókóddal) → nyilvános profil-URL, név, snippet, követőszám ha a snippetben szerepel. Csak jelölt-lista; közönségadat nincs. | ingyenes |
| **LLM-dúsítás** | bio/snippet → kategória, érdeklődés, értékek, életstílus, hangnem, nem; a közönség kor/nem csak *jelölt becslés*. Háttér sorrendben: `ANTHROPIC_API_KEY` → Claude Code CLI (`claude -p`, előfizetéssel) → Ollama (offline) → szabályalapú kulcsszó. A `notes` mező mutatja, melyik írta. | API-díj / 0 |
| **CSV / JSON import** | bármely adatszolgáltató (Modash, HypeAuditor, Upfluence, Kolsquare, ügynökségi lista) exportja. Sablon: `data/import_sablon.csv` vagy a GUI-ból. Város → megye/koordináta automatikus. | a szolgáltató díja |
| **Modash Discovery API** | adapter (`influradar/modash.py`): hely + követő szűrés náluk, profil-riporttal közönség-demográfia. `MODASH_API_KEY` a `.env`-ben. Mezőleképezés best-effort, éles kulccsal tesztelendő. | ~$300+/hó |
| **Kézi felvitel** | ismert profil rögzítése, utána dúsítás | – |

Fizetős alternatívák, amelyekhez csak import van: HypeAuditor, Upfluence, Kolsquare, CreatorIQ, Heepsy (utóbbi olcsóbb, ~$50/hó, van hely-szűrője).

## CLI

```
.venv/bin/python -m influradar collect "Graz" --radius 60 --sources ddg,demo --max-towns 6 --enrich
.venv/bin/python -m influradar collect "Kraków, Poland" --radius 40 --sources ddg --platforms instagram,tiktok --terms fitness
.venv/bin/python -m influradar import export.csv --source modash
.venv/bin/python -m influradar enrich --max 30
.venv/bin/python -m influradar search collection_id=1 categories=fitness aud_age=18-24 aud_age_min=35 --csv > list.csv
.venv/bin/python -m influradar demo -n 600        # régi, országos magyar demo (opcionális)
.venv/bin/python -m influradar stats | clear demo
```

## Importformátum

Oszlopok: `platform, handle, name, city, bio, followers, engagement_rate, language, gender, age, categories, interests, values, lifestyles, tones, audience_age, audience_gender, audience_locations, audience_interests, contact_email, price_estimate_huf, verified`.
Listák pontosvesszővel (`fitness;food`), eloszlások `18-24:40;25-34:35` alakban (%). Kulcsok a `influradar/taxonomy.py` szótáraiból; ismeretlen kulcs megmarad, de a szűrő nem találja.

## Adatvédelem

Csak 127.0.0.1-en fut. Külső hívások: Nominatim (helykeresés, 1 kérés/mp), Overpass (városlista, lemez-cache a `data/cache` mappában), DuckDuckGo. A DDG-felderítés keresőmotor-találatot dolgoz fel, platformoldalt nem tölt le. Az LLM-dúsítás a bio-t elküldi a választott háttérnek (Ollama esetén nem hagyja el a gépet). Személyes adatot tartalmazó listák kezelésére a céges GDPR-szabályzat vonatkozik; a `Napló` fül minden importot, dúsítást és törlést rögzít.

## Struktúra

```
influradar/geo.py        Nominatim helykeresés, Overpass városok, ország→nyelv, Haversine, magyar CSV tartalék
influradar/taxonomy.py   szótárak + célcsoport-előbeállítások (HU/EN)
influradar/db.py         SQLite, normalizálás, szűrőmotor, CSV
influradar/demo.py       szintetikus adat
influradar/discover.py   DuckDuckGo felderítés városlistára, 30+ nyelv kulcsszavai
influradar/modash.py     fizetős API adapter
influradar/llm.py        dúsítás (api/cli/ollama/rules)
influradar/webapp.py     HTTP API   ·  influradar/ui.html  egyoldalas felület (Leaflet)
```
