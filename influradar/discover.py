"""Ingyenes felderítés: DuckDuckGo `site:` keresés → nyilvános profil-URL-ek és snippetek, az ország nyelvén + angolul.
Nem tölt le platformoldalt (ToS-barát). Eredmény: jelöltek (source='ddg'), közönségadat nélkül – LLM-dúsítás címkézi."""
from __future__ import annotations

import re
import time
from typing import Callable

from . import geo

SITE = {
    "instagram": ("site:instagram.com", re.compile(r"instagram\.com/([A-Za-z0-9_.]{2,30})/?(?:\?|$)")),
    "tiktok": ("site:tiktok.com", re.compile(r"tiktok\.com/@([A-Za-z0-9_.]{2,30})")),
    "youtube": ("site:youtube.com", re.compile(r"youtube\.com/(?:@|c/|user/)([A-Za-z0-9_.\-]{2,40})")),
    "facebook": ("site:facebook.com", re.compile(r"facebook\.com/([A-Za-z0-9.]{3,50})/?(?:\?|$)")),
}
SKIP = {"p", "reel", "reels", "explore", "stories", "tv", "accounts", "watch", "shorts", "results", "channel", "playlist", "hashtag", "tag", "groups",
        "events", "pages", "share", "video", "discover", "music", "search", "about", "legal", "help", "privacy", "public", "directory", "locations"}

# nyelv → keresőszavak (az első a legfontosabb; a limit szűkíti)
TERMS = {
    "en": ["influencer", "content creator", "blogger", "collab"],
    "hu": ["influencer", "tartalomgyártó", "vlogger", "együttműködés"],
    "de": ["influencer", "content creator", "blogger", "kooperation"],
    "fr": ["influenceur", "créateur de contenu", "blogueuse", "collab"],
    "es": ["influencer", "creador de contenido", "blogger", "colaboración"],
    "it": ["influencer", "content creator", "blogger", "collaborazione"],
    "pt": ["influenciador", "criador de conteúdo", "blogger", "parceria"],
    "nl": ["influencer", "contentcreator", "blogger", "samenwerking"],
    "pl": ["influencer", "twórca", "blogerka", "współpraca"],
    "cs": ["influencer", "tvůrce obsahu", "blogerka", "spolupráce"],
    "sk": ["influencer", "tvorca obsahu", "blogerka", "spolupráca"],
    "ro": ["influencer", "creator de conținut", "blogger", "colaborare"],
    "bg": ["инфлуенсър", "създател на съдържание", "блогър"],
    "el": ["influencer", "δημιουργός περιεχομένου", "blogger"],
    "hr": ["influencer", "kreator sadržaja", "blogerica", "suradnja"],
    "sl": ["influencer", "ustvarjalec vsebin", "blogerka", "sodelovanje"],
    "sr": ["influenser", "kreator sadržaja", "blogerka", "saradnja"],
    "sv": ["influencer", "kreatör", "bloggare", "samarbete"],
    "da": ["influencer", "content creator", "blogger", "samarbejde"],
    "no": ["influenser", "innholdsskaper", "blogger", "samarbeid"],
    "fi": ["vaikuttaja", "sisällöntuottaja", "bloggaaja", "yhteistyö"],
    "et": ["mõjuisik", "sisulooja", "blogija"], "lv": ["influenceris", "satura veidotājs", "blogere"], "lt": ["influenceris", "turinio kūrėjas", "tinklaraštininkė"],
    "uk": ["інфлюенсер", "блогер", "контент-мейкер"], "ru": ["инфлюенсер", "блогер"], "tr": ["influencer", "içerik üreticisi", "blogger"],
    "is": ["áhrifavaldur", "bloggari"], "sq": ["influencer", "krijues përmbajtje", "bloger"], "mk": ["инфлуенсер", "блогер"], "ka": ["ინფლუენსერი", "ბლოგერი"],
}
MIN_FOLLOWERS = 200
FOLLOWER_RE = re.compile(r"([\d.,\s]+?)\s*([KMkm]|tis\.|ezer|mil\.?)?\s*(?:követő|followers?|abonnés|seguidores|follower|abonnenten|volgers|obserwujących|sledujících|urmăritori|"
                         r"feliratkozó|subscribers?|abonn|iscritti|suscriptores|subskrybentów|odberateľov|pratilaca|följare|følgere|seuraajaa|подписчик|підписник)", re.I)


def _followers(text: str) -> int | None:
    m = FOLLOWER_RE.search(text or "")
    if not m:
        return None
    num, suf = m.group(1).strip(" .,"), (m.group(2) or "").lower()
    num = num.replace(" ", " ")
    try:
        if re.fullmatch(r"\d{1,3}([.,\s]\d{3})+", num):
            val = float(re.sub(r"[.,\s]", "", num))
        else:
            val = float(num.replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    mult = 1e6 if suf.startswith("m") else 1e3 if suf and (suf[0] in "ke" or suf.startswith("tis")) else 1
    return int(val * mult)


class SearchBlocked(RuntimeError):
    """A keresőmotor sorozatban nem ad eredményt (bot-védelem / rate limit)."""


def _brave(q: str, country: str | None, lang: str, n: int) -> list[dict]:
    """Brave Search API – hivatalos, kulcsos (BRAVE_SEARCH_API_KEY), ~1 kérés/mp az ingyenes sávban."""
    import json
    import os
    import urllib.parse
    import urllib.request
    params = {"q": q, "count": min(n, 20), "search_lang": lang if lang in ("en", "de", "fr", "es", "it", "nl", "pl", "pt", "hu", "cs", "sk", "ro", "sv", "da", "fi", "no", "tr", "el", "bg", "hr", "uk", "ru") else "en"}
    if country and len(country) == 2:
        params["country"] = country.upper()
    req = urllib.request.Request("https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(params),
                                 headers={"Accept": "application/json", "X-Subscription-Token": os.environ["BRAVE_SEARCH_API_KEY"], "User-Agent": "influenszer-radar/0.2"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    return [{"href": x.get("url", ""), "title": x.get("title", ""), "body": x.get("description", "")} for x in (data.get("web") or {}).get("results", [])]


def search_backend() -> str:
    import os
    return "brave" if os.environ.get("BRAVE_SEARCH_API_KEY") else "ddg"


def _search(ddg, q: str, region: str, country: str | None, lang: str, n: int) -> list[dict]:
    if search_backend() == "brave":
        return _brave(q, country, lang, n)
    return list(ddg.text(q, region=region, safesearch="moderate", backend="auto", max_results=n))


def terms_for(country: str | None, limit: int = 3) -> tuple[list[str], str]:
    """(kulcsszavak országnyelven + angolul, DDG-régió)."""
    lang, region = geo.country_lang(country)
    local = TERMS.get(lang, [])[:limit]
    en = [t for t in TERMS["en"][:limit] if t not in local]
    return local + en, region


def discover(towns: list[dict], platforms: list[str] | None = None, extra_terms: list[str] | None = None, terms_per_lang: int = 2,
             max_results: int = 25, progress: Callable[[str], None] | None = None, stop: Callable[[], bool] | None = None,
             pause: float = 2.5, max_consecutive_failures: int = 5) -> list[dict]:
    """towns: [{name, name_local?, lat, lon, county, country, ...}] – a gyűjtés körzetének városai.
    SearchBlocked-ot dob, ha a keresőmotor sorozatban (max_consecutive_failures) nem ad választ – bot-védelem / rate limit."""
    from ddgs import DDGS  # lazy import

    platforms = platforms or ["instagram", "tiktok", "youtube"]
    seen: dict[str, dict] = {}
    ddg = DDGS()
    backend = search_backend()
    failures = 0
    done_queries: set[str] = set()
    uniq_towns: list[dict] = []
    for t in towns:  # azonos nevű duplikátumok (pl. Nominatim + Overpass ugyanarra a városra) kiszűrése
        if not any(geo.norm(u["name"]) == geo.norm(t["name"]) for u in uniq_towns):
            uniq_towns.append(t)
    if progress:
        progress(f"keresőháttér / search backend: {backend}")
    for town in uniq_towns:
        if stop and stop():
            break
        names = [town.get("name_local") or town["name"]]
        if geo.norm(town["name"]) != geo.norm(names[0]):
            names.append(town["name"])
        lang, region = geo.country_lang(town.get("country"))
        terms, _ = terms_for(town.get("country"), terms_per_lang)
        terms = terms + [t for t in (extra_terms or []) if t]
        for plat in platforms:
            if plat not in SITE:
                continue
            site, rx = SITE[plat]
            for name in names:
                for term in terms:
                    if stop and stop():
                        break
                    q = f'{site} "{name}" {term}'
                    if q in done_queries:
                        continue
                    done_queries.add(q)
                    if progress:
                        progress(f"{town['name']} · {plat} · {term}")
                    try:
                        hits = _search(ddg, q, region, town.get("country"), lang, max_results)
                        failures = 0
                    except Exception as e:  # noqa: BLE001
                        failures += 1
                        msg = str(e)[:90]
                        if progress:
                            progress(f"  ⚠ ({failures}/{max_consecutive_failures}) {msg}")
                        if failures >= max_consecutive_failures:
                            raise SearchBlocked(f"A keresőmotor ({backend}) {failures} egymás utáni lekérdezésre nem adott választ – valószínűleg bot-védelem / "
                                                f"rate limit erről az IP-ről. Próbáld néhány óra múlva, vagy állíts be BRAVE_SEARCH_API_KEY-t. / "
                                                f"Search engine ({backend}) returned nothing for {failures} consecutive queries – likely bot protection / rate limit. "
                                                f"Retry in a few hours or set BRAVE_SEARCH_API_KEY. Utolsó hiba / last error: {msg}") from e
                        time.sleep(min(60, pause * 2 ** failures))
                        continue
                    for h in hits:
                        url = h.get("href") or h.get("url") or ""
                        m = rx.search(url)
                        if not m:
                            continue
                        handle = m.group(1)
                        if handle.lower() in SKIP:
                            continue
                        key = f"{plat}:{handle.lower()}"
                        title, body = h.get("title", ""), h.get("body", "")
                        rec = seen.setdefault(key, {"platform": plat, "handle": handle, "url": url, "city": town["name"], "county": town.get("county"),
                                                    "region": town.get("region", ""), "country": town.get("country"), "lat": town.get("lat"), "lon": town.get("lon"),
                                                    "source": "ddg" if backend == "ddg" else "brave", "language": lang,
                                                    "name": re.split(r"\s[•|(@\-–]", title)[0].strip()[:80], "bio": body[:600], "followers": None, "notes": f"találat / hit: {q}"})
                        if rec.get("followers") is None:
                            rec["followers"] = _followers(title + " " + body)
                        if rec.get("followers") is not None and rec["followers"] < MIN_FOLLOWERS:
                            seen.pop(key, None)
                    time.sleep(pause)
    return list(seen.values())
