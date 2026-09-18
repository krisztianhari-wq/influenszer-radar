"""Földrajz Európa-szinten: Nominatim helykeresés, Overpass városlista sugáron belül, Haversine. Magyar CSV = offline gyorsítótár/tartalék."""
from __future__ import annotations

import csv
import json
import time
import unicodedata
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

from .paths import data_dir, resources

DATA = resources() / "data"
UA = {"User-Agent": "influenszer-radar/0.2 (local marketing tool; contact via repo)"}
_last_nominatim = 0.0
LAST_ERROR = ""

REGIONS: dict[str, list[str]] = {
    "Közép-Magyarország": ["Budapest", "Pest"], "Közép-Dunántúl": ["Fejér", "Komárom-Esztergom", "Veszprém"],
    "Nyugat-Dunántúl": ["Győr-Moson-Sopron", "Vas", "Zala"], "Dél-Dunántúl": ["Baranya", "Somogy", "Tolna"],
    "Észak-Magyarország": ["Borsod-Abaúj-Zemplén", "Heves", "Nógrád"], "Észak-Alföld": ["Hajdú-Bihar", "Jász-Nagykun-Szolnok", "Szabolcs-Szatmár-Bereg"],
    "Dél-Alföld": ["Bács-Kiskun", "Békés", "Csongrád-Csanád"],
}
COUNTY_REGION: dict[str, str] = {c: r for r, cs in REGIONS.items() for c in cs}

# ország → (fő nyelv, DDG régiókód)
COUNTRY_LANG: dict[str, tuple[str, str]] = {
    "hu": ("hu", "hu-hu"), "at": ("de", "at-de"), "de": ("de", "de-de"), "ch": ("de", "ch-de"), "li": ("de", "ch-de"),
    "gb": ("en", "uk-en"), "ie": ("en", "ie-en"), "mt": ("en", "wt-wt"), "fr": ("fr", "fr-fr"), "be": ("nl", "be-nl"), "lu": ("fr", "fr-fr"), "mc": ("fr", "fr-fr"),
    "es": ("es", "es-es"), "pt": ("pt", "pt-pt"), "it": ("it", "it-it"), "sm": ("it", "it-it"), "nl": ("nl", "nl-nl"),
    "pl": ("pl", "pl-pl"), "cz": ("cs", "cz-cs"), "sk": ("sk", "sk-sk"), "ro": ("ro", "ro-ro"), "md": ("ro", "ro-ro"), "bg": ("bg", "bg-bg"),
    "gr": ("el", "gr-el"), "cy": ("el", "gr-el"), "hr": ("hr", "hr-hr"), "si": ("sl", "wt-wt"), "rs": ("sr", "wt-wt"), "ba": ("hr", "wt-wt"), "me": ("sr", "wt-wt"), "mk": ("mk", "wt-wt"), "al": ("sq", "wt-wt"), "xk": ("sq", "wt-wt"),
    "se": ("sv", "se-sv"), "dk": ("da", "dk-da"), "no": ("no", "no-no"), "fi": ("fi", "fi-fi"), "is": ("is", "wt-wt"),
    "ee": ("et", "ee-et"), "lv": ("lv", "lv-lv"), "lt": ("lt", "lt-lt"), "ua": ("uk", "ua-uk"), "by": ("ru", "ru-ru"), "tr": ("tr", "tr-tr"), "ge": ("ka", "wt-wt"),
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower().strip()


def country_lang(cc: str | None) -> tuple[str, str]:
    return COUNTRY_LANG.get((cc or "").lower(), ("en", "wt-wt"))


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --- offline magyar lista ------------------------------------------------------
@lru_cache(maxsize=1)
def settlements() -> list[dict]:
    out = []
    with open(DATA / "telepulesek.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.append({"name": r["name"], "county": r["county"], "region": COUNTY_REGION.get(r["county"], ""), "country": "hu",
                        "lat": float(r["lat"]), "lon": float(r["lon"]), "population": int(r["population"]), "display": f'{r["name"]}, {r["county"]}, Magyarország'})
    return out


def find_settlement(name: str) -> dict | None:
    if not name:
        return None
    key = norm(name.split(",")[0])
    idx = {norm(s["name"]): s for s in settlements()}
    if key in idx:
        return idx[key]
    if key.startswith("budapest"):
        return idx["budapest"]
    return None


# --- Nominatim ------------------------------------------------------------------
def _nominatim(params: dict) -> list[dict]:
    global _last_nominatim
    wait = 1.05 - (time.time() - _last_nominatim)
    if wait > 0:
        time.sleep(wait)
    _last_nominatim = time.time()
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}", headers=UA)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _place(hit: dict, fallback_name: str = "") -> dict:
    a = hit.get("address", {})
    name = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or hit.get("name") or fallback_name
    county = a.get("county") or a.get("state_district") or a.get("province") or a.get("region") or ""
    county = county.replace(" vármegye", "").replace(" megye", "")
    state = a.get("state") or ""
    cc = (a.get("country_code") or "").lower()
    return {"name": name, "name_local": hit.get("name") or name, "county": county or state, "state": state, "region": COUNTY_REGION.get(county, state), "country": cc,
            "country_name": a.get("country", ""), "lat": float(hit["lat"]), "lon": float(hit["lon"]),
            "population": int(hit.get("extratags", {}).get("population") or 0), "display": hit.get("display_name", name), "source": "nominatim"}


def search_places(q: str, limit: int = 6, lang: str = "hu") -> list[dict]:
    """Autocomplete: európai városok/települések. Offline magyar találat elöl."""
    out = []
    s = find_settlement(q)
    if s:
        out.append(s)
    if len(q.strip()) < 3:
        return out
    try:
        hits = _nominatim({"q": q, "format": "jsonv2", "limit": limit, "addressdetails": 1, "extratags": 1, "accept-language": f"{lang},en",
                           "featuretype": "settlement", "viewbox": "-25,72,45,34", "bounded": 0})
    except Exception:  # noqa: BLE001
        return out
    seen = {(round(p["lat"], 2), round(p["lon"], 2)) for p in out}
    for h in hits:
        if h.get("addresstype") not in (None, "city", "town", "village", "municipality", "borough", "suburb", "county", "state", "administrative", "hamlet"):
            continue
        p = _place(h, q)
        k = (round(p["lat"], 2), round(p["lon"], 2))
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out[:limit]


def geocode(name: str, lang: str = "hu") -> dict | None:
    r = search_places(name, 1, lang)
    return r[0] if r else None


# --- Overpass: városok a körön belül ----------------------------------------------
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
CACHE = data_dir() / "cache"


def _overpass(query: str) -> dict:
    last = None
    for url in OVERPASS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": query}).encode(), headers=UA)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode())
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"overpass: {last!r}")


def towns_within(lat: float, lon: float, km: float, limit: int = 12, min_pop: int = 0) -> list[dict]:
    """OSM place=city|town csomópontok a sugáron belül, népesség szerint csökkenő. Lemez-cache; tartalék: magyar CSV."""
    global LAST_ERROR
    CACHE.mkdir(parents=True, exist_ok=True)
    cf = CACHE / f"towns_{lat:.3f}_{lon:.3f}_{int(km)}.json"
    towns: list[dict] = []
    if cf.exists():
        towns = json.loads(cf.read_text())
    else:
        query = f'[out:json][timeout:40];node["place"~"^(city|town)$"](around:{int(km * 1000)},{lat},{lon});out;'
        try:
            data = _overpass(query)
            for el in data.get("elements", []):
                t = el.get("tags", {})
                try:
                    pop = int(str(t.get("population", "0")).replace(" ", "").split(".")[0] or 0)
                except ValueError:
                    pop = 0
                towns.append({"name": t.get("name", ""), "name_local": t.get("name", ""), "name_en": t.get("name:en", ""), "lat": el["lat"], "lon": el["lon"],
                              "population": pop, "county": t.get("addr:county") or t.get("is_in:county") or "", "country": (t.get("addr:country") or t.get("is_in:country_code") or "").lower(),
                              "place": t.get("place")})
            if towns:
                cf.write_text(json.dumps(towns, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            LAST_ERROR = str(e)
    if not towns:
        towns = [dict(s, name_local=s["name"]) for s in settlements() if haversine_km(lat, lon, s["lat"], s["lon"]) <= km]
    for t in towns:
        t["distance_km"] = round(haversine_km(lat, lon, t["lat"], t["lon"]), 1)
    towns = [t for t in towns if t["name"] and t["population"] >= min_pop]
    towns.sort(key=lambda t: (-t["population"], t["distance_km"]))
    return towns[:limit]


def reverse_country(lat: float, lon: float) -> dict:
    """Országkód + megye a középponthoz (Overpass-csomópontoknak gyakran nincs országcímkéje)."""
    try:
        global _last_nominatim
        wait = 1.05 - (time.time() - _last_nominatim)
        if wait > 0:
            time.sleep(wait)
        _last_nominatim = time.time()
        q = urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "addressdetails": 1})
        req = urllib.request.Request(f"https://nominatim.openstreetmap.org/reverse?{q}", headers=UA)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _place(json.loads(resp.read().decode()))
    except Exception:  # noqa: BLE001
        return {}


def assign_countries(towns: list[dict], default_cc: str = "", progress=None) -> list[dict]:
    """Ország + megye a városokhoz fordított geokódolással (cache-elve). Hiba esetén a középpont országa."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cf = CACHE / "reverse.json"
    cache = json.loads(cf.read_text()) if cf.exists() else {}
    for t in towns:
        key = f"{t['lat']:.3f},{t['lon']:.3f}"
        if key not in cache:
            if progress:
                progress(f"geo: {t['name']}")
            p = reverse_country(t["lat"], t["lon"])
            cache[key] = {"country": p.get("country", ""), "county": p.get("county", ""), "state": p.get("state", ""), "name_ui": p.get("name", "")}
        c = cache[key]
        t["country"] = t.get("country") or c["country"] or default_cc
        t["county"] = t.get("county") or c["county"] or c["state"]
        t["region"] = COUNTY_REGION.get(t["county"], c.get("state", ""))
        if t["country"] == "hu" and c.get("name_ui"):
            t["name"] = c["name_ui"]
    cf.write_text(json.dumps(cache, ensure_ascii=False))
    return towns


def settlements_within(lat: float, lon: float, km: float) -> list[dict]:
    """Offline magyar települések a sugáron belül, távolság szerint (demo-generátorhoz)."""
    return sorted((dict(s, distance_km=round(haversine_km(lat, lon, s["lat"], s["lon"]), 1)) for s in settlements()
                   if haversine_km(lat, lon, s["lat"], s["lon"]) <= km), key=lambda s: s["distance_km"])
