"""SQLite tár + szűrőmotor. Egy influenszer = egy sor, listák/térképek JSON-ban."""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

from . import geo
from .taxonomy import AGE_BUCKETS, TIERS

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "radar.sqlite"

LIST_FIELDS = ("categories", "interests", "values", "lifestyles", "tones", "audience_interests")
DICT_FIELDS = ("audience_age", "audience_gender", "audience_locations")
JSON_FIELDS = LIST_FIELDS + DICT_FIELDS

COLUMNS = [
    "id", "platform", "handle", "name", "url", "bio", "city", "county", "region", "country", "lat", "lon", "collection_id",
    "followers", "engagement_rate", "avg_views", "posts_per_week", "language", "gender", "age",
    "categories", "interests", "values", "lifestyles", "tones",
    "audience_age", "audience_gender", "audience_locations", "audience_interests", "audience_language",
    "contact_email", "price_estimate_huf", "verified", "source", "enriched", "notes", "updated_at",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS influencers (
  id TEXT PRIMARY KEY, platform TEXT, handle TEXT, name TEXT, url TEXT, bio TEXT,
  city TEXT, county TEXT, region TEXT, country TEXT, lat REAL, lon REAL, collection_id INTEGER,
  followers INTEGER, engagement_rate REAL, avg_views INTEGER, posts_per_week REAL,
  language TEXT, gender TEXT, age INTEGER,
  categories TEXT, interests TEXT, "values" TEXT, lifestyles TEXT, tones TEXT,
  audience_age TEXT, audience_gender TEXT, audience_locations TEXT, audience_interests TEXT, audience_language TEXT,
  contact_email TEXT, price_estimate_huf INTEGER, verified INTEGER DEFAULT 0, source TEXT, enriched INTEGER DEFAULT 0,
  notes TEXT, updated_at REAL
);
CREATE INDEX IF NOT EXISTS ix_platform ON influencers(platform);
CREATE INDEX IF NOT EXISTS ix_county ON influencers(county);
CREATE TABLE IF NOT EXISTS lists (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, created_at REAL, filters TEXT);
CREATE TABLE IF NOT EXISTS list_items (list_id INTEGER, influencer_id TEXT, added_at REAL, PRIMARY KEY (list_id, influencer_id));
CREATE TABLE IF NOT EXISTS audit (ts REAL, action TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS collections (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, lat REAL, lon REAL, radius_km REAL, country TEXT,
  towns TEXT, sources TEXT, status TEXT, created_at REAL, count INTEGER DEFAULT 0, log TEXT);
"""


def _dumps(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False)


def _loads(v: Any, default: Any):
    if v in (None, ""):
        return default
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except Exception:  # noqa: BLE001
        return default


def _split(v: Any) -> list[str]:
    """CSV-importhoz: 'a;b, c' → ['a','b','c']."""
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if v in (None, ""):
        return []
    s = str(v).strip()
    if s.startswith("["):
        return _loads(s, [])
    return [x.strip() for x in s.replace(";", ",").split(",") if x.strip()]


def _dist(v: Any) -> dict[str, float]:
    """'18-24:40;25-34:35' vagy JSON → {bucket: %}."""
    if isinstance(v, dict):
        return {str(k): float(x) for k, x in v.items()}
    if v in (None, ""):
        return {}
    s = str(v).strip()
    if s.startswith("{"):
        return {str(k): float(x) for k, x in _loads(s, {}).items()}
    out = {}
    for part in s.replace(",", ";").split(";"):
        if ":" in part:
            k, x = part.split(":", 1)
            try:
                out[k.strip()] = float(x.strip().rstrip("%"))
            except ValueError:
                pass
    return out


def normalize(rec: dict) -> dict:
    """Bármilyen bejövő rekord (CSV/JSON/API) → egységes sor. Település → megye/régió/koordináta."""
    r: dict[str, Any] = {c: rec.get(c) for c in COLUMNS}
    r["platform"] = (rec.get("platform") or "instagram").lower().strip()
    r["handle"] = (rec.get("handle") or rec.get("username") or "").lstrip("@").strip()
    if not r["handle"] and rec.get("url"):
        r["handle"] = rec["url"].rstrip("/").split("/")[-1].lstrip("@")
    r["id"] = rec.get("id") or f"{r['platform']}:{r['handle'].lower()}"
    if not r["url"] and r["handle"]:
        base = {"instagram": "https://www.instagram.com/{h}/", "tiktok": "https://www.tiktok.com/@{h}", "youtube": "https://www.youtube.com/@{h}",
                "facebook": "https://www.facebook.com/{h}", "x": "https://x.com/{h}", "linkedin": "https://www.linkedin.com/in/{h}", "twitch": "https://www.twitch.tv/{h}"}
        r["url"] = base.get(r["platform"], "https://{h}").format(h=r["handle"])
    for k in LIST_FIELDS:
        r[k] = [x.lower() for x in _split(rec.get(k))]
    for k in DICT_FIELDS:
        r[k] = _dist(rec.get(k))
    for k in ("followers", "avg_views", "age", "price_estimate_huf"):
        try:
            r[k] = int(float(rec.get(k))) if rec.get(k) not in (None, "") else None
        except (TypeError, ValueError):
            r[k] = None
    for k in ("engagement_rate", "posts_per_week"):
        try:
            r[k] = float(str(rec.get(k)).rstrip("%")) if rec.get(k) not in (None, "") else None
        except (TypeError, ValueError):
            r[k] = None
    r["verified"] = 1 if str(rec.get("verified", "")).lower() in ("1", "true", "yes", "igen") else 0
    r["enriched"] = 1 if str(rec.get("enriched", "")).lower() in ("1", "true") else 0
    r["gender"] = (rec.get("gender") or "").lower() or None
    r["language"] = (rec.get("language") or "hu").lower()
    r["source"] = rec.get("source") or "import"
    r["country"] = (rec.get("country") or "").lower() or None
    r["collection_id"] = rec.get("collection_id")
    # földrajz: ha nincs koordináta, offline magyar lista, majd Nominatim
    if r.get("city") and (r.get("lat") in (None, "") or r.get("lon") in (None, "")):
        s = geo.find_settlement(r["city"]) or (geo.geocode(r["city"]) if rec.get("_geocode", True) else None)
        if s:
            r["city"] = s["name"]
            r["county"] = r.get("county") or s.get("county")
            r["country"] = r.get("country") or s.get("country")
            r["lat"], r["lon"] = s["lat"], s["lon"]
    if r.get("county") and not r.get("region"):
        r["region"] = geo.COUNTY_REGION.get(r["county"], "")
    if r.get("county") and not r.get("country") and r["county"] in geo.COUNTY_REGION:
        r["country"] = "hu"
    for k in ("lat", "lon"):
        try:
            r[k] = float(r[k]) if r.get(k) not in (None, "") else None
        except (TypeError, ValueError):
            r[k] = None
    r["updated_at"] = time.time()
    return r


def tier(followers: int | None) -> str:
    if not followers:
        return ""
    for k, (lo, hi) in TIERS.items():
        if lo <= followers < hi:
            return k
    return ""


class Store:
    def __init__(self, path: Path | str = DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        have = {r[1] for r in self.con.execute("PRAGMA table_info(influencers)")}
        for col, typ in (("country", "TEXT"), ("collection_id", "INTEGER")):
            if col not in have:
                self.con.execute(f"ALTER TABLE influencers ADD COLUMN {col} {typ}")
        self.con.commit()

    # --- gyűjtések ---------------------------------------------------------
    def create_collection(self, label: str, lat: float, lon: float, radius_km: float, country: str, sources: list[str]) -> int:
        cur = self.con.execute("INSERT INTO collections (label, lat, lon, radius_km, country, towns, sources, status, created_at, count, log) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                               (label, lat, lon, radius_km, country, "[]", _dumps(sources), "running", time.time(), 0, ""))
        self.con.commit()
        return cur.lastrowid

    def update_collection(self, cid: int, **fields) -> None:
        if "towns" in fields:
            fields["towns"] = _dumps(fields["towns"])
        sets = ", ".join(f"{k}=?" for k in fields)
        self.con.execute(f"UPDATE collections SET {sets} WHERE id=?", [*fields.values(), cid])
        self.con.commit()

    def collections(self) -> list[dict]:
        out = []
        for r in self.con.execute("SELECT * FROM collections ORDER BY created_at DESC"):
            d = dict(r)
            d["towns"] = _loads(d.get("towns"), [])
            d["sources"] = _loads(d.get("sources"), [])
            d["count"] = self.con.execute("SELECT COUNT(*) FROM influencers WHERE collection_id=?", (d["id"],)).fetchone()[0]
            out.append(d)
        return out

    def collection(self, cid: int) -> dict | None:
        r = self.con.execute("SELECT * FROM collections WHERE id=?", (cid,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["towns"], d["sources"] = _loads(d.get("towns"), []), _loads(d.get("sources"), [])
        return d

    def delete_collection(self, cid: int, with_items: bool = True) -> int:
        n = 0
        if with_items:
            n = self.con.execute("DELETE FROM influencers WHERE collection_id=?", (cid,)).rowcount
        self.con.execute("DELETE FROM collections WHERE id=?", (cid,))
        self.con.commit()
        self.log("collection_delete", f"#{cid}, {n} profil törölve")
        return n

    # --- írás -----------------------------------------------------------
    def upsert(self, recs: Iterable[dict], source: str | None = None) -> int:
        n = 0
        cur = self.con.cursor()
        for rec in recs:
            r = normalize(rec)
            if source:
                r["source"] = source
            if not r["handle"]:
                continue
            row = {k: (_dumps(v) if k in JSON_FIELDS else v) for k, v in r.items()}
            cols = ", ".join(f'"{c}"' for c in COLUMNS)
            ph = ", ".join(f":{c}" for c in COLUMNS)
            upd = ", ".join(f'"{c}"=COALESCE(excluded."{c}", influencers."{c}")' for c in COLUMNS if c != "id")
            cur.execute(f"INSERT INTO influencers ({cols}) VALUES ({ph}) ON CONFLICT(id) DO UPDATE SET {upd}", row)
            n += 1
        self.con.commit()
        self.log("upsert", f"{n} rekord, forrás={source or 'vegyes'}")
        return n

    def update_fields(self, iid: str, fields: dict) -> None:
        sets = ", ".join(f'"{k}"=?' for k in fields)
        vals = [(_dumps(v) if k in JSON_FIELDS else v) for k, v in fields.items()]
        self.con.execute(f"UPDATE influencers SET {sets}, updated_at=? WHERE id=?", [*vals, time.time(), iid])
        self.con.commit()

    def delete(self, iid: str) -> None:
        self.con.execute("DELETE FROM influencers WHERE id=?", (iid,))
        self.con.execute("DELETE FROM list_items WHERE influencer_id=?", (iid,))
        self.con.commit()

    def clear_source(self, source: str) -> int:
        cur = self.con.execute("DELETE FROM influencers WHERE source=?", (source,))
        self.con.commit()
        self.log("clear", f"forrás={source}, {cur.rowcount} törölve")
        return cur.rowcount

    def log(self, action: str, detail: str) -> None:
        self.con.execute("INSERT INTO audit VALUES (?,?,?)", (time.time(), action, detail))
        self.con.commit()

    # --- olvasás ----------------------------------------------------------
    def _row(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        for k in LIST_FIELDS:
            d[k] = _loads(d.get(k), [])
        for k in DICT_FIELDS:
            d[k] = _loads(d.get(k), {})
        d["tier"] = tier(d.get("followers"))
        return d

    def all(self) -> list[dict]:
        return [self._row(r) for r in self.con.execute("SELECT * FROM influencers")]

    def get(self, iid: str) -> dict | None:
        r = self.con.execute("SELECT * FROM influencers WHERE id=?", (iid,)).fetchone()
        return self._row(r) if r else None

    def stats(self) -> dict:
        c = self.con
        return {"total": c.execute("SELECT COUNT(*) FROM influencers").fetchone()[0],
                "by_platform": {r[0]: r[1] for r in c.execute("SELECT platform, COUNT(*) FROM influencers GROUP BY 1")},
                "by_source": {r[0]: r[1] for r in c.execute("SELECT source, COUNT(*) FROM influencers GROUP BY 1")},
                "enriched": c.execute("SELECT COUNT(*) FROM influencers WHERE enriched=1").fetchone()[0]}

    # --- listák -----------------------------------------------------------
    def create_list(self, name: str, filters: dict, ids: list[str]) -> int:
        cur = self.con.execute("INSERT INTO lists (name, created_at, filters) VALUES (?,?,?)", (name, time.time(), _dumps(filters)))
        lid = cur.lastrowid
        self.con.executemany("INSERT OR IGNORE INTO list_items VALUES (?,?,?)", [(lid, i, time.time()) for i in ids])
        self.con.commit()
        return lid

    def lists(self) -> list[dict]:
        return [{"id": r["id"], "name": r["name"], "created_at": r["created_at"], "filters": _loads(r["filters"], {}),
                 "count": self.con.execute("SELECT COUNT(*) FROM list_items WHERE list_id=?", (r["id"],)).fetchone()[0]}
                for r in self.con.execute("SELECT * FROM lists ORDER BY created_at DESC")]

    def list_items(self, lid: int) -> list[dict]:
        rows = self.con.execute("SELECT i.* FROM influencers i JOIN list_items li ON li.influencer_id=i.id WHERE li.list_id=? ORDER BY i.followers DESC", (lid,))
        return [self._row(r) for r in rows]

    def delete_list(self, lid: int) -> None:
        self.con.execute("DELETE FROM lists WHERE id=?", (lid,))
        self.con.execute("DELETE FROM list_items WHERE list_id=?", (lid,))
        self.con.commit()

    def audit(self, limit: int = 200) -> list[dict]:
        return [dict(r) for r in self.con.execute("SELECT * FROM audit ORDER BY ts DESC LIMIT ?", (limit,))]


# --- szűrés ----------------------------------------------------------------

def _as_list(v: Any) -> list[str]:
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x)]
    return [x for x in str(v).split(",") if x]


def _num(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def search(store: Store, f: dict) -> dict:
    """Szűrőparaméterek (mind opcionális):
    center (település), radius_km, county[], region[], platform[], tier[], followers_min/max, er_min, language, gender, age_min/max,
    categories[], interests[], values[], lifestyles[], tones[], match=any|all (pszichográfia),
    aud_age (bucket) + aud_age_min (%), aud_gender + aud_gender_min, aud_loc (település) + aud_loc_min, aud_interests[],
    q (szabad szó: név/handle/bio), enriched_only, sort, limit.
    """
    rows = store.all()
    out = []
    center = None
    if f.get("lat") not in (None, "") and f.get("lon") not in (None, ""):
        center = {"name": f.get("center") or "", "lat": float(f["lat"]), "lon": float(f["lon"])}
    elif f.get("center"):
        center = geo.find_settlement(f["center"]) or geo.geocode(f["center"])
    countries = set(x.lower() for x in _as_list(f.get("country")))
    cid = _num(f.get("collection_id"))
    radius = _num(f.get("radius_km"))
    counties = set(_as_list(f.get("county")))
    regions = set(_as_list(f.get("region")))
    platforms = set(x.lower() for x in _as_list(f.get("platform")))
    tiers = set(_as_list(f.get("tier")))
    fmin, fmax, ermin = _num(f.get("followers_min")), _num(f.get("followers_max")), _num(f.get("er_min"))
    amin, amax = _num(f.get("age_min")), _num(f.get("age_max"))
    match_all = (f.get("match") or "any") == "all"
    psycho = {k: set(x.lower() for x in _as_list(f.get(k))) for k in ("categories", "interests", "values", "lifestyles", "tones", "audience_interests")}
    q = (f.get("q") or "").lower().strip()
    aud_age, aud_age_min = f.get("aud_age"), _num(f.get("aud_age_min")) or 0
    aud_gender, aud_gender_min = f.get("aud_gender"), _num(f.get("aud_gender_min")) or 0
    aud_loc, aud_loc_min = f.get("aud_loc"), _num(f.get("aud_loc_min")) or 0
    aud_loc_key = geo.norm(aud_loc) if aud_loc else None

    for r in rows:
        if cid is not None and r.get("collection_id") != int(cid):
            continue
        if countries and (r.get("country") or "") not in countries:
            continue
        if platforms and r["platform"] not in platforms:
            continue
        if counties and r.get("county") not in counties:
            continue
        if regions and r.get("region") not in regions:
            continue
        if tiers and r["tier"] not in tiers:
            continue
        if fmin is not None and (r.get("followers") or 0) < fmin:
            continue
        if fmax is not None and (r.get("followers") or 0) > fmax:
            continue
        if ermin is not None and (r.get("engagement_rate") or 0) < ermin:
            continue
        if f.get("language") and (r.get("language") or "") != f["language"]:
            continue
        if f.get("gender") and (r.get("gender") or "") != f["gender"]:
            continue
        if amin is not None and (r.get("age") is None or r["age"] < amin):
            continue
        if amax is not None and (r.get("age") is None or r["age"] > amax):
            continue
        if f.get("enriched_only") in ("1", True, "true") and not r.get("enriched"):
            continue
        if q and q not in " ".join(str(r.get(k) or "") for k in ("name", "handle", "bio", "city")).lower():
            continue
        # földrajz: körön belül
        r["distance_km"] = None
        if center and radius is not None:
            if r.get("lat") is None or r.get("lon") is None:
                continue
            d = geo.haversine_km(center["lat"], center["lon"], r["lat"], r["lon"])
            if d > radius:
                continue
            r["distance_km"] = round(d, 1)
        elif center and radius is None:
            if geo.norm(r.get("city") or "") != geo.norm(center["name"]):
                continue
            r["distance_km"] = 0.0
        # pszichográfia / kategória
        ok = True
        for k, wanted in psycho.items():
            if not wanted:
                continue
            have = set(r.get(k) or [])
            hit = wanted <= have if match_all else bool(wanted & have)
            if not hit:
                ok = False
                break
        if not ok:
            continue
        # közönség
        if aud_age and aud_age in AGE_BUCKETS and (r.get("audience_age") or {}).get(aud_age, 0) < aud_age_min:
            continue
        if aud_gender and (r.get("audience_gender") or {}).get(aud_gender, 0) < aud_gender_min:
            continue
        if aud_loc_key:
            share = sum(v for k, v in (r.get("audience_locations") or {}).items() if geo.norm(k) == aud_loc_key)
            if share < aud_loc_min:
                continue
        out.append(r)

    sort = f.get("sort") or ("distance" if center and radius is not None else "followers")
    keyf = {"followers": lambda r: -(r.get("followers") or 0), "er": lambda r: -(r.get("engagement_rate") or 0),
            "distance": lambda r: (r.get("distance_km") if r.get("distance_km") is not None else 1e9),
            "name": lambda r: (r.get("name") or r.get("handle") or "").lower()}.get(sort, lambda r: -(r.get("followers") or 0))
    out.sort(key=keyf)
    total = len(out)
    limit = int(_num(f.get("limit")) or 500)
    facets = {"county": {}, "country": {}, "platform": {}, "source": {}}
    for r in out:
        for k in facets:
            v = r.get(k) or ""
            if v:
                facets[k][v] = facets[k].get(v, 0) + 1
    return {"total": total, "center": center, "radius_km": radius, "items": out[:limit], "facets": facets}


def to_csv(items: list[dict]) -> str:
    buf = io.StringIO()
    cols = ["platform", "handle", "name", "url", "city", "county", "country", "distance_km", "followers", "tier", "engagement_rate",
            "avg_views", "language", "gender", "age", "categories", "interests", "values", "lifestyles", "tones",
            "audience_age", "audience_gender", "audience_locations", "audience_interests", "contact_email", "price_estimate_huf", "source", "enriched", "bio"]
    w = csv.writer(buf)
    w.writerow(cols)
    for r in items:
        w.writerow(["; ".join(r[c]) if isinstance(r.get(c), list) else
                    "; ".join(f"{k}:{v}" for k, v in r[c].items()) if isinstance(r.get(c), dict) else r.get(c, "") for c in cols])
    return buf.getvalue()


def import_file(store: Store, path: str | Path, source: str | None = None) -> int:
    p = Path(path)
    text = p.read_text(encoding="utf-8-sig")
    if p.suffix.lower() == ".json":
        data = json.loads(text)
        recs = data if isinstance(data, list) else data.get("items") or data.get("influencers") or []
    else:
        recs = list(csv.DictReader(io.StringIO(text)))
    return store.upsert(recs, source=source or f"import:{p.name}")
