"""Elérhetőségek kiegészítése szabályos forrásokból: bio/snippet-kivonatolás, platformok közti összekapcsolás,
saját weboldal / linktree lekérése (mailto:, tel:, social linkek), opcionális célzott webkeresés. Platformoldalt nem tölt le."""
from __future__ import annotations

import html
import re
import time
import urllib.parse
import urllib.request
from typing import Callable

from . import geo

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+\s?(?:@|\(at\)|\[at\]|\{at\}|\s at \s)\s?[A-Za-z0-9.\-]+\s?(?:\.|\(dot\)|\[dot\])\s?[A-Za-z]{2,10}", re.I)
PHONE_RE = re.compile(r"(?<![\d,.])(\+\d{1,3}[\s().\-]?\d[\d\s().\-]{6,16}\d|\b0[1-9][\d\s().\-]{6,14}\d)(?![\d,.]*\s*(?:követ|follow|abonn|seguid|subscri|feliratk|posts|bejegyz|likes|views|nézés))", re.I)
URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+|\b(?:linktr\.ee|beacons\.ai|bio\.link|allmylinks\.com|carrd\.co|linkin\.bio|taplink\.cc|solo\.to|lnk\.bio|bento\.me)/[A-Za-z0-9_.\-/]+", re.I)
PLATFORM_DOMAINS = {
    "instagram": re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})", re.I), "tiktok": re.compile(r"tiktok\.com/@([A-Za-z0-9_.]{2,30})", re.I),
    "youtube": re.compile(r"youtube\.com/(?:@|c/|user/|channel/)([A-Za-z0-9_.\-]{2,40})", re.I), "facebook": re.compile(r"facebook\.com/([A-Za-z0-9.]{3,50})", re.I),
    "x": re.compile(r"(?:twitter|x)\.com/([A-Za-z0-9_]{2,20})", re.I), "linkedin": re.compile(r"linkedin\.com/in/([A-Za-z0-9\-_%]{2,60})", re.I),
    "twitch": re.compile(r"twitch\.tv/([A-Za-z0-9_]{3,30})", re.I),
}
MENTION_RE = {  # csak explicit említés: "TikTok: @xy", "insta @xy", "yt: xy" – szóhatárral, kötelező @ vagy elválasztó
    "tiktok": re.compile(r"\b(?:tiktok|tt)\b\s*(?:[:\-–]\s*@?|@)([A-Za-z0-9_.]{3,30})", re.I),
    "instagram": re.compile(r"\b(?:instagram|insta|ig)\b\s*(?:[:\-–]\s*@?|@)([A-Za-z0-9_.]{3,30})", re.I),
    "youtube": re.compile(r"\b(?:youtube|yt)\b\s*(?:[:\-–]\s*@?|@)([A-Za-z0-9_.\-]{3,40})", re.I),
    "x": re.compile(r"\b(?:twitter|x)\b\s*(?:[:\-–]\s*@?|@)([A-Za-z0-9_]{3,20})", re.I),
}
TLDS = {"com", "net", "org", "info", "biz", "eu", "io", "co", "me", "tv", "de", "at", "ch", "hu", "nl", "be", "fr", "es", "it", "pt", "pl", "cz", "sk", "ro", "bg", "gr", "hr", "si", "rs",
        "se", "dk", "no", "fi", "ee", "lv", "lt", "uk", "ie", "ua", "tr", "lu", "li", "is", "mt", "cy", "ba", "mk", "al", "me", "md", "us", "ca", "au", "nz", "mail", "email", "agency", "media",
        "studio", "shop", "store", "online", "site", "art", "design", "digital", "live", "life", "blog", "photography", "fit", "fitness", "beauty", "app", "dev", "xyz", "club", "team", "pro", "one"}
SKIP_HOSTS = ("instagram.com", "tiktok.com", "youtube.com", "youtu.be", "facebook.com", "fb.com", "twitter.com", "x.com", "linkedin.com", "twitch.tv",
              "google.", "bing.com", "duckduckgo.com", "wikipedia.org", "apple.com", "spotify.com", "amazon.")
LINK_HUB = ("linktr.ee", "beacons.ai", "bio.link", "allmylinks.com", "carrd.co", "linkin.bio", "taplink.cc", "solo.to", "lnk.bio", "bento.me")
CONTACT_TERMS = {"en": "email OR contact OR management OR booking", "hu": "email OR elérhetőség OR kapcsolat OR menedzsment", "de": "email OR kontakt OR management OR booking",
                 "nl": "email OR contact OR management OR boekingen", "fr": "email OR contact OR management OR booking", "es": "email OR contacto OR management",
                 "it": "email OR contatti OR management", "pl": "email OR kontakt OR współpraca", "cs": "email OR kontakt OR spolupráce", "sk": "email OR kontakt OR spolupráca",
                 "ro": "email OR contact OR colaborare", "hr": "email OR kontakt OR suradnja", "sv": "email OR kontakt OR samarbete", "da": "email OR kontakt", "fi": "email OR yhteystiedot"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; influenszer-radar/0.2; local marketing tool)"}


def _norm_email(e: str) -> str:
    e = re.sub(r"\s?(?:\(at\)|\[at\]|\{at\}|\s at \s)\s?", "@", e, flags=re.I)
    e = re.sub(r"\s?(?:\(dot\)|\[dot\])\s?", ".", e, flags=re.I)
    e = e.replace(" ", "").strip(".").lower()
    if "@" in e:  # URL-maradék levágása a domain végéről: "gmail.com.watch" → "gmail.com"
        local, dom = e.rsplit("@", 1)
        parts = dom.split(".")
        for i in range(len(parts) - 1, 0, -1):
            if parts[i] in TLDS:
                return f"{local}@{'.'.join(parts[:i + 1])}"
        return ""  # ismeretlen végződés → inkább eldobjuk
    return e


def _norm_phone(p: str) -> str | None:
    digits = re.sub(r"\D", "", p)
    if not 9 <= len(digits) <= 15:
        return None
    return ("+" if p.strip().startswith("+") else "") + digits


def extract(text: str) -> dict:
    """Szöveg → {emails, phones, links{platform: handle}, websites}."""
    text = html.unescape(text or "")
    out = {"emails": [], "phones": [], "links": {}, "websites": []}
    for m in EMAIL_RE.findall(text):
        e = _norm_email(m)
        if re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,10}", e) and not e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) and e not in out["emails"]:
            out["emails"].append(e)
    for m in PHONE_RE.findall(text):
        p = _norm_phone(m)
        if p and p not in out["phones"]:
            out["phones"].append(p)
    for plat, rx in PLATFORM_DOMAINS.items():
        for h in rx.findall(text):
            if h.lower() not in ("p", "reel", "reels", "explore", "stories", "watch", "shorts", "share", "results", "channel", "hashtag"):
                out["links"].setdefault(plat, h.rstrip("/"))
    for plat, rx in MENTION_RE.items():
        for h in rx.findall(text):
            if plat not in out["links"] and not h.lower().startswith(("http", "com")):
                out["links"][plat] = h.rstrip(".")
    for u in URL_RE.findall(text):
        u = u if u.lower().startswith("http") else "https://" + u
        host = urllib.parse.urlparse(u).netloc.lower()
        if host and not any(s in host for s in SKIP_HOSTS) and u not in out["websites"]:
            out["websites"].append(u.rstrip(".,);"))
    return out


def fetch_site(url: str, timeout: float = 8.0, max_bytes: int = 400_000) -> dict:
    """Nyilvános saját weboldal / link-hub letöltése: mailto:, tel:, social linkek, szöveges e-mail/telefon. Platformdomaint nem tölt le."""
    host = urllib.parse.urlparse(url).netloc.lower()
    if any(s in host for s in SKIP_HOSTS):
        return {}
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ctype = r.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype and "json" not in ctype:
            return {}
        body = r.read(max_bytes).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    found = extract(re.sub(r"<[^>]+>", " ", body))
    for m in re.findall(r"mailto:([^\"'?\s<>]+)", body, re.I):
        e = _norm_email(html.unescape(m))
        if "@" in e and e not in found["emails"]:
            found["emails"].insert(0, e)
    for m in re.findall(r"tel:([+\d\s().\-]{7,25})", body, re.I):
        p = _norm_phone(m)
        if p and p not in found["phones"]:
            found["phones"].insert(0, p)
    for m in re.findall(r"href=[\"']([^\"']+)", body, re.I):
        sub = extract(html.unescape(m))
        for plat, h in sub["links"].items():
            found["links"].setdefault(plat, h)
    found["websites"] = [w for w in found["websites"] if urllib.parse.urlparse(w).netloc.lower() != host][:5]
    return found


def crosslink(rows: list[dict]) -> dict[str, dict]:
    """Azonos handle (pont/aláhúzás nélkül) vagy azonos név+város más platformon → links kiegészítés. → {id: {platform: handle}}"""
    def key_h(r):
        return re.sub(r"[._\-]", "", geo.norm(r.get("handle") or ""))
    def key_n(r):
        n = geo.norm(r.get("name") or "")
        return (n, geo.norm(r.get("city") or "")) if len(n) > 5 and " " in n else None
    by_h: dict[str, list[dict]] = {}
    by_n: dict[tuple, list[dict]] = {}
    for r in rows:
        if key_h(r):
            by_h.setdefault(key_h(r), []).append(r)
        if key_n(r):
            by_n.setdefault(key_n(r), []).append(r)
    add: dict[str, dict] = {}
    for groups in (by_h.values(), by_n.values()):
        for g in groups:
            if len(g) < 2:
                continue
            for r in g:
                for o in g:
                    if o is not r and o["platform"] != r["platform"]:
                        add.setdefault(r["id"], {}).setdefault(o["platform"], o["handle"])
    return add


def contact_search(rec: dict, ddg, progress: Callable[[str], None] | None = None) -> dict:
    """Célzott webkeresés: "handle" + kapcsolat-szavak az ország nyelvén. A találatok snippetjéből kivonatol; platformoldalt nem nyit meg."""
    from .discover import _search
    lang, region = geo.country_lang(rec.get("country"))
    terms = CONTACT_TERMS.get(lang, CONTACT_TERMS["en"])
    q = f'"{rec["handle"]}" ({terms})'
    if progress:
        progress(f"  🔎 {q}")
    hits = _search(ddg, q, region, rec.get("country"), lang, 10)
    merged = {"emails": [], "phones": [], "links": {}, "websites": []}
    for h in hits:
        url = h.get("href") or ""
        if not any(s in url.lower() for s in SKIP_HOSTS) or any(s in url.lower() for s in LINK_HUB):
            pass
        f = extract(" ".join([h.get("title", ""), h.get("body", ""), url]))
        for k in ("emails", "phones", "websites"):
            merged[k] += [x for x in f[k] if x not in merged[k]]
        for plat, hd in f["links"].items():
            merged["links"].setdefault(plat, hd)
    return merged


def apply(rec: dict, found: dict) -> dict:
    """Talált adatok → frissítendő mezők (a meglévőt nem írja felül, csak kiegészíti)."""
    upd: dict = {}
    if found.get("emails") and not rec.get("contact_email"):
        upd["contact_email"] = found["emails"][0]
    if found.get("phones") and not rec.get("phone"):
        upd["phone"] = found["phones"][0]
    if found.get("websites") and not rec.get("website"):
        upd["website"] = found["websites"][0]
    links = dict(rec.get("links") or {})
    for plat, h in (found.get("links") or {}).items():
        if plat != rec.get("platform") and plat not in links:
            links[plat] = h
    if links != (rec.get("links") or {}):
        upd["links"] = links
    return upd


def enrich_contacts(store, ids: list[str], web_search: bool = False, fetch_sites: bool = True, progress: Callable[[str], None] | None = None,
                    stop: Callable[[], bool] | None = None, pause: float = 2.0) -> dict:
    """Teljes menet: kivonatolás → összekapcsolás → weboldal-lekérés → (opció) célzott keresés. → statisztika."""
    rows = store.all()
    cross = crosslink(rows)
    byid = {r["id"]: r for r in rows}
    stats = {"processed": 0, "email": 0, "phone": 0, "website": 0, "links": 0, "sites_fetched": 0, "searched": 0}
    ddg = None
    if web_search:
        from ddgs import DDGS
        ddg = DDGS()
    for i, iid in enumerate(ids, 1):
        if stop and stop():
            break
        rec = byid.get(iid) or store.get(iid)
        if not rec:
            continue
        found = extract(" ".join(str(rec.get(k) or "") for k in ("bio", "notes", "name")))
        found["links"].update({k: v for k, v in cross.get(iid, {}).items() if k not in found["links"]})
        if rec.get("website") and rec["website"] not in found["websites"]:
            found["websites"].insert(0, rec["website"])
        if fetch_sites:
            for site in found["websites"][:2]:
                try:
                    f = fetch_site(site)
                    stats["sites_fetched"] += 1
                    for k in ("emails", "phones"):
                        found[k] += [x for x in f.get(k, []) if x not in found[k]]
                    for plat, h in f.get("links", {}).items():
                        found["links"].setdefault(plat, h)
                    if progress:
                        progress(f"  🌐 {site} → {len(f.get('emails', []))} email, {len(f.get('links', {}))} link")
                except Exception as e:  # noqa: BLE001
                    if progress:
                        progress(f"  🌐 {site}: {str(e)[:60]}")
        if web_search and ddg is not None and not (found["emails"] or rec.get("contact_email")):
            try:
                f = contact_search(rec, ddg, progress)
                stats["searched"] += 1
                for k in ("emails", "phones", "websites"):
                    found[k] += [x for x in f[k] if x not in found[k]]
                for plat, h in f["links"].items():
                    found["links"].setdefault(plat, h)
                time.sleep(pause)
            except Exception as e:  # noqa: BLE001
                if progress:
                    progress(f"  🔎 hiba: {str(e)[:60]}")
                time.sleep(pause * 2)
        upd = apply(rec, found)
        if upd:
            store.update_fields(iid, upd)
            for k, sk in (("contact_email", "email"), ("phone", "phone"), ("website", "website"), ("links", "links")):
                if k in upd:
                    stats[sk] += 1
        stats["processed"] += 1
        if progress and (i % 5 == 0 or upd):
            progress(f"[{i}/{len(ids)}] {rec['handle']}: " + (", ".join(f"{k}={v if k != 'links' else list(v)}" for k, v in upd.items()) or "—"))
    return stats
