"""Helyi webes felület + JSON API – stdlib http.server, csak 127.0.0.1. Európai helykeresés, körzeti gyűjtés igény szerint. sadrobot."""
from __future__ import annotations

import csv as _csv
import io
import json
import threading
import time
import traceback
import urllib.parse
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import discover, geo, llm, modash
from .db import Store, search, to_csv
from .taxonomy import (AGE_BUCKETS, CATEGORIES, GENDERS, INTERESTS, LIFESTYLES, PLATFORMS, TARGET_GROUPS, TIERS, TONES, VALUES, as_options)

STORE = Store()
STORE.con.execute("UPDATE collections SET status='interrupted' WHERE status='running'")
STORE.con.commit()
JOBS: dict[str, dict] = {}
from .paths import resources

HTML_PATH = Path(__file__).resolve().parent / "ui.html"
TEMPLATE_PATH = resources() / "data" / "import_sablon.csv"


def _job(fn, *args, **kw) -> str:
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = {"id": jid, "status": "running", "log": [], "result": None, "started": time.time(), "stop": False}

    def run():
        try:
            res = fn(*args, progress=lambda m: JOBS[jid]["log"].append(m), stop=lambda: JOBS[jid]["stop"], **kw)
            JOBS[jid].update(status="done", result=res)
        except Exception as e:  # noqa: BLE001
            JOBS[jid].update(status="error", result=str(e))
            JOBS[jid]["log"].append(traceback.format_exc()[-800:])
    threading.Thread(target=run, daemon=True).start()
    return jid


def job_collect(b: dict, progress, stop):
    """Helyszín + sugár → városok → források (ddg / modash) → opcionális LLM-dúsítás. Minden rekord collection_id-vel."""
    lat, lon, radius = float(b["lat"]), float(b["lon"]), float(b.get("radius_km") or 30)
    label = b.get("label") or f"{b.get('name', '')} · {int(radius)} km"
    sources = b.get("sources") or ["ddg"]
    center_cc = (b.get("country") or geo.reverse_country(lat, lon).get("country") or "").lower()
    cid = STORE.create_collection(label, lat, lon, radius, center_cc, sources)
    try:
        progress(f"[{cid}] {label} · országkód: {center_cc or '?'}")
        towns = geo.towns_within(lat, lon, radius, limit=int(b.get("max_towns") or 8), min_pop=int(b.get("min_pop") or 0))
        if not any(geo.haversine_km(lat, lon, t["lat"], t["lon"]) < 3 for t in towns):
            towns.insert(0, {"name": b.get("name") or label, "name_local": b.get("name_local") or b.get("name"), "lat": lat, "lon": lon, "population": 0,
                             "county": b.get("county") or "", "country": center_cc})
        geo.assign_countries(towns, center_cc, progress)
        STORE.update_collection(cid, towns=towns)
        progress("városok / towns: " + ", ".join(f"{t['name']} ({t['country']})" for t in towns))
        total = 0
        if "modash" in sources and modash.available():
            for t in towns[:3]:
                for plat in b.get("platforms") or ["instagram"]:
                    try:
                        recs = modash.search(plat, t.get("name_local") or t["name"])
                        for r in recs:
                            r.update(collection_id=cid, country=t["country"], lat=t["lat"], lon=t["lon"], county=t.get("county"))
                        total += STORE.upsert(recs, source="modash")
                        progress(f"modash {plat} {t['name']}: {len(recs)}")
                    except Exception as e:  # noqa: BLE001
                        progress(f"modash hiba: {e}")
        blocked = None
        if "ddg" in sources:
            try:
                recs = discover.discover(towns, b.get("platforms") or ["instagram", "tiktok", "youtube"], b.get("terms") or [],
                                         terms_per_lang=int(b.get("terms_per_lang") or 2), progress=progress, stop=stop)
            except discover.SearchBlocked as e:
                blocked = str(e)
                progress("⛔ " + blocked)
                recs = []
            src = "brave" if discover.search_backend() == "brave" else "ddg"
            for r in recs:
                r["collection_id"] = cid
                r["_geocode"] = False
            total += STORE.upsert(recs, source=src)
            progress(f"{src}: {len(recs)} jelölt / candidates")
        STORE.update_collection(cid, status="blocked" if blocked else ("stopped" if stop() else "done"), count=total, log=blocked or "")
        if b.get("enrich") and "ddg" in sources:
            ids = [r["id"] for r in STORE.all() if r.get("collection_id") == cid and not r.get("enriched")][: int(b.get("enrich_max") or 40)]
            progress(f"LLM-dúsítás: {len(ids)} profil · {llm.backends()[0]}")
            job_enrich(ids, progress, stop)
        STORE.log("collect", f"#{cid} {label}: {total} profil, források={','.join(sources)}")
        return {"collection_id": cid, "count": total, "towns": [t["name"] for t in towns], "blocked": blocked}
    except Exception:
        STORE.update_collection(cid, status="error")
        raise


def job_enrich(ids, progress, stop=None):
    done = 0
    for i, iid in enumerate(ids, 1):
        if stop and stop():
            break
        rec = STORE.get(iid)
        if not rec:
            continue
        fields, backend = llm.enrich(rec)
        STORE.update_fields(iid, fields)
        done += 1
        progress(f"[{i}/{len(ids)}] {rec['handle']} ← {backend}")
    STORE.log("enrich", f"{done} profil dúsítva")
    return {"enriched": done}


def meta(lang: str) -> dict:
    return {
        "platforms": PLATFORMS, "tiers": {k: list(v) for k, v in TIERS.items()}, "age_buckets": AGE_BUCKETS,
        "genders": as_options(GENDERS, lang), "categories": as_options(CATEGORIES, lang), "interests": as_options(INTERESTS, lang),
        "values": as_options(VALUES, lang), "lifestyles": as_options(LIFESTYLES, lang), "tones": as_options(TONES, lang),
        "target_groups": [{"key": k, "label": v["label"][0 if lang == "hu" else 1], "filters": v["filters"]} for k, v in TARGET_GROUPS.items()],
        "stats": STORE.stats(), "llm_backends": llm.backends(), "modash": modash.available(), "collections": STORE.collections(),
        "search_backend": discover.search_backend(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "InfluRadar/0.2"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode())

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads((self.rfile.read(n) if n else b"").decode() or "{}")
        except json.JSONDecodeError:
            return {}

    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = {k: (v if len(v) > 1 else v[0]) for k, v in urllib.parse.parse_qs(u.query).items()}
        lang = q.get("lang", "hu")
        try:
            if u.path == "/":
                return self._send(200, HTML_PATH.read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/meta":
                return self._json(meta(lang))
            if u.path == "/api/places":
                return self._json(geo.search_places(q.get("q", ""), 7, lang))
            if u.path == "/api/towns":
                t = geo.towns_within(float(q["lat"]), float(q["lon"]), float(q.get("radius_km") or 30), int(q.get("limit") or 8))
                return self._json({"towns": t, "error": geo.LAST_ERROR})
            if u.path == "/api/search":
                return self._json(search(STORE, q))
            if u.path == "/api/export.csv":
                res = search(STORE, dict(q, limit=100000))
                return self._send(200, to_csv(res["items"]).encode("utf-8-sig"), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="influencer-radar.csv"'})
            if u.path.startswith("/api/influencer/"):
                rec = STORE.get(urllib.parse.unquote(u.path.split("/", 3)[3]))
                return self._json(rec) if rec else self._json({"error": "not found"}, 404)
            if u.path.startswith("/api/jobs/"):
                return self._json(JOBS.get(u.path.rsplit("/", 1)[1], {"status": "unknown"}))
            if u.path == "/api/collections":
                return self._json(STORE.collections())
            if u.path == "/api/lists":
                return self._json(STORE.lists())
            if u.path.startswith("/api/lists/"):
                lid = int(u.path.rsplit("/", 1)[1])
                if q.get("format") == "csv":
                    return self._send(200, to_csv(STORE.list_items(lid)).encode("utf-8-sig"), "text/csv; charset=utf-8", {"Content-Disposition": f'attachment; filename="list-{lid}.csv"'})
                return self._json(STORE.list_items(lid))
            if u.path == "/api/audit":
                return self._json(STORE.audit())
            if u.path == "/api/template.csv":
                return self._send(200, TEMPLATE_PATH.read_bytes(), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="import_template.csv"'})
            return self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e), "trace": traceback.format_exc()[-600:]}, 500)

    def do_POST(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        b = self._body()
        try:
            if u.path == "/api/collect":
                if b.get("lat") in (None, "") or b.get("lon") in (None, ""):
                    return self._json({"error": "lat/lon required"}, 400)
                return self._json({"job": _job(job_collect, b)})
            if u.path == "/api/import":
                recs = list(_csv.DictReader(io.StringIO(b["csv"]))) if b.get("csv") else (b.get("items") or [])
                for r in recs:
                    if b.get("collection_id"):
                        r["collection_id"] = b["collection_id"]
                return self._json({"added": STORE.upsert(recs, source=b.get("source") or "import")})
            if u.path == "/api/influencer":
                STORE.upsert([b], source=b.get("source") or "manual")
                return self._json({"ok": True})
            if u.path == "/api/enrich":
                ids = b.get("ids") or [r["id"] for r in search(STORE, dict(b.get("filters") or {}, limit=100000))["items"]]
                if b.get("only_unenriched", True):
                    ids = [i for i in ids if not (STORE.get(i) or {}).get("enriched")]
                mx = int(b.get("max") or 50)
                return self._json({"job": _job(job_enrich, ids[:mx]), "count": min(len(ids), mx)})
            if u.path == "/api/lists":
                lid = STORE.create_list(b.get("name") or f"List {time.strftime('%Y-%m-%d %H:%M')}", b.get("filters") or {}, b.get("ids") or [])
                return self._json({"id": lid})
            if u.path.startswith("/api/jobs/") and u.path.endswith("/stop"):
                jid = u.path.split("/")[3]
                if jid in JOBS:
                    JOBS[jid]["stop"] = True
                return self._json({"ok": True})
            return self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e), "trace": traceback.format_exc()[-600:]}, 500)

    def do_DELETE(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        try:
            if u.path.startswith("/api/collections/"):
                return self._json({"deleted": STORE.delete_collection(int(u.path.rsplit("/", 1)[1]))})
            if u.path.startswith("/api/source/"):
                return self._json({"deleted": STORE.clear_source(urllib.parse.unquote(u.path.rsplit("/", 1)[1]))})
            if u.path.startswith("/api/influencer/"):
                STORE.delete(urllib.parse.unquote(u.path.split("/", 3)[3]))
                return self._json({"ok": True})
            if u.path.startswith("/api/lists/"):
                STORE.delete_list(int(u.path.rsplit("/", 1)[1]))
                return self._json({"ok": True})
            return self._json({"error": "not found"}, 404)
        except Exception as e:  # noqa: BLE001
            return self._json({"error": str(e)}, 500)


def serve(host="127.0.0.1", port=8790, open_browser=False):
    import socket
    for p in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer((host, p), Handler)
            break
        except OSError:
            continue
    else:
        raise SystemExit(f"nincs szabad port {port}–{port + 19} / no free port")
    url = f"http://{host}:{srv.server_address[1]}"
    print(f"Influencer Radar → {url}   (Ctrl+C: stop)")
    if open_browser:
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
