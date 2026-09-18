"""Modash Discovery API adapter (fizetős; MODASH_API_KEY). Csak akkor fut, ha van kulcs. Dokumentáció: https://docs.modash.io
Hely-, követő-, közönség-életkor/nem-szűrőket a Modash oldalán végzi; a többit a helyi motor. Az API-válasz mezői változhatnak – a leképezés best-effort."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

BASE = os.environ.get("MODASH_BASE", "https://api.modash.io/v1")


def available() -> bool:
    return bool(os.environ.get("MODASH_API_KEY"))


def _req(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['MODASH_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def location_id(platform: str, name: str) -> int | None:
    data = _req("GET", f"/{platform}/locations?{urllib.parse.urlencode({'query': name, 'limit': 5})}")
    locs = data.get("locations") or data.get("data") or []
    return locs[0]["id"] if locs else None


def search(platform: str, city: str, followers_min: int = 1000, followers_max: int = 1_000_000, page: int = 0,
           aud_age: list[str] | None = None, aud_gender: str | None = None, limit: int = 15) -> list[dict]:
    loc = location_id(platform, city)
    filt: dict = {"influencer": {"followers": {"min": followers_min, "max": followers_max}, "location": [loc] if loc else []},
                  "audience": {}}
    if aud_age:
        filt["audience"]["age"] = aud_age
    if aud_gender:
        filt["audience"]["gender"] = {"id": aud_gender.upper(), "weight": 0.5}
    data = _req("POST", f"/{platform}/search", {"page": page, "limit": limit, "sort": {"field": "followers", "direction": "desc"}, "filter": filt})
    out = []
    for it in data.get("lookalikes") or data.get("directs") or data.get("results") or []:
        p = it.get("profile", it)
        out.append({"platform": platform, "handle": p.get("username") or p.get("handle"), "name": p.get("fullname"), "url": p.get("url"),
                    "followers": p.get("followers"), "engagement_rate": (p.get("engagementRate") or 0) * 100, "city": city,
                    "bio": p.get("bio"), "source": "modash", "verified": p.get("isVerified")})
    return out


def report(platform: str, handle: str) -> dict:
    """Részletes profil-riport (közönség-demográfia). Külön kreditbe kerül."""
    data = _req("GET", f"/{platform}/profile/{urllib.parse.quote(handle)}/report").get("profile", {})
    aud = data.get("audience", {})
    def pct(items, key="code"):
        return {str(x.get(key)): round(100 * float(x.get("weight", 0)), 1) for x in items or []}
    return {"followers": data.get("profile", {}).get("followers"), "engagement_rate": (data.get("profile", {}).get("engagementRate") or 0) * 100,
            "audience_age": pct(aud.get("ages")), "audience_gender": pct(aud.get("genders")), "audience_locations": pct(aud.get("geoCities"), "name"),
            "audience_interests": [x.get("name", "").lower() for x in aud.get("interests") or []][:10],
            "gender": (data.get("profile", {}).get("gender") or "").lower() or None, "enriched": 1}
