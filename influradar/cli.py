"""CLI: gui | demo | import | discover | enrich | search | export | stats | clear."""
from __future__ import annotations

import argparse
import json
import sys

from . import demo, llm
from .db import Store, import_file, search, to_csv


def main(argv=None):
    ap = argparse.ArgumentParser(prog="influradar", description="Influenszer Radar – helyi influenszer-kereső")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gui", help="webes felület indítása")
    g.add_argument("--port", type=int, default=8790)
    d = sub.add_parser("demo", help="szintetikus demo-adatok betöltése")
    d.add_argument("-n", type=int, default=600)
    i = sub.add_parser("import", help="CSV/JSON import")
    i.add_argument("path")
    i.add_argument("--source")
    dc = sub.add_parser("collect", help="körzeti gyűjtés: helyszín (bármely európai város) + sugár → források")
    dc.add_argument("place", help="pl. 'Graz' vagy 'Kraków, Poland'")
    dc.add_argument("--radius", type=float, default=30)
    dc.add_argument("--sources", default="ddg", help="ddg,demo,modash")
    dc.add_argument("--platforms", default="instagram,tiktok,youtube")
    dc.add_argument("--terms", default="")
    dc.add_argument("--max-towns", type=int, default=8)
    dc.add_argument("--enrich", action="store_true")
    e = sub.add_parser("enrich", help="LLM-dúsítás a még nem címkézett profilokra")
    e.add_argument("--max", type=int, default=50)
    e.add_argument("--source")
    s = sub.add_parser("search", help="szűrés; kulcs=érték párok, pl. center=Graz radius_km=40 collection_id=1 categories=fitness aud_age=18-24 aud_age_min=35")
    s.add_argument("kv", nargs="*")
    s.add_argument("--csv", action="store_true")
    sub.add_parser("stats")
    c = sub.add_parser("clear", help="forrás törlése (demo, ddg, modash, import:...)")
    c.add_argument("source")
    a = ap.parse_args(argv)
    st = Store()

    if a.cmd == "gui":
        from .webapp import serve
        serve(port=a.port)
    elif a.cmd == "demo":
        print(st.upsert(demo.generate(a.n), source="demo"), "demo rekord betöltve")
    elif a.cmd == "import":
        print(import_file(st, a.path, a.source), "rekord importálva")
    elif a.cmd == "collect":
        from . import geo
        from .webapp import job_collect
        p = geo.geocode(a.place)
        if not p:
            sys.exit(f"nem található / not found: {a.place}")
        print(f"{p['display']} ({p['country']})", file=sys.stderr)
        res = job_collect({"lat": p["lat"], "lon": p["lon"], "name": p["name"], "name_local": p.get("name_local"), "country": p["country"], "county": p.get("county"),
                           "radius_km": a.radius, "sources": a.sources.split(","), "platforms": a.platforms.split(","), "terms": [t for t in a.terms.split(",") if t],
                           "max_towns": a.max_towns, "enrich": a.enrich}, progress=lambda m: print("·", m, file=sys.stderr), stop=lambda: False)
        print(json.dumps(res, ensure_ascii=False))
    elif a.cmd == "enrich":
        rows = [r for r in st.all() if not r.get("enriched") and (not a.source or r.get("source") == a.source)][: a.max]
        print("háttér:", llm.backends()[0], file=sys.stderr)
        for r in rows:
            fields, b = llm.enrich(r)
            st.update_fields(r["id"], fields)
            print(f"{r['handle']:30s} {b:12s} {fields.get('categories')}")
    elif a.cmd == "search":
        f = dict(kv.split("=", 1) for kv in a.kv)
        res = search(st, f)
        if a.csv:
            sys.stdout.write(to_csv(res["items"]))
        else:
            print(f"{res['total']} találat")
            for r in res["items"][:50]:
                print(f"{r['platform']:9s} @{r['handle']:28s} {r.get('city') or '':18s} {r.get('distance_km') if r.get('distance_km') is not None else '':>6} km "
                      f"{(r.get('followers') or 0):>9,} ER {r.get('engagement_rate') or 0:>5} {','.join(r.get('categories') or [])}")
    elif a.cmd == "stats":
        print(json.dumps(st.stats(), ensure_ascii=False, indent=1))
    elif a.cmd == "clear":
        print(st.clear_source(a.source), "törölve")
