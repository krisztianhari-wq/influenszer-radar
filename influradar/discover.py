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


def terms_for(country: str | None, limit: int = 3) -> tuple[list[str], str]:
    """(kulcsszavak országnyelven + angolul, DDG-régió)."""
    lang, region = geo.country_lang(country)
    local = TERMS.get(lang, [])[:limit]
    en = [t for t in TERMS["en"][:limit] if t not in local]
    return local + en, region


def discover(towns: list[dict], platforms: list[str] | None = None, extra_terms: list[str] | None = None, terms_per_lang: int = 2,
             max_results: int = 25, progress: Callable[[str], None] | None = None, stop: Callable[[], bool] | None = None) -> list[dict]:
    """towns: [{name, name_local?, lat, lon, county, country, ...}] – a gyűjtés körzetének városai."""
    from ddgs import DDGS  # lazy import

    platforms = platforms or ["instagram", "tiktok", "youtube"]
    seen: dict[str, dict] = {}
    ddg = DDGS()
    for town in towns:
        if stop and stop():
            break
        names = {town.get("name_local") or town["name"], town["name"]}
        terms, region = terms_for(town.get("country"), terms_per_lang)
        terms = terms + [t for t in (extra_terms or []) if t]
        for plat in platforms:
            if plat not in SITE:
                continue
            site, rx = SITE[plat]
            for name in names:
                for term in terms:
                    q = f'{site} "{name}" {term}'
                    if progress:
                        progress(f"{town['name']} · {plat} · {term}")
                    try:
                        hits = list(ddg.text(q, region=region, safesearch="moderate", max_results=max_results))
                    except Exception as e:  # noqa: BLE001
                        if progress:
                            progress(f"  ⚠ {e}")
                        time.sleep(3)
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
                                                    "source": "ddg", "language": geo.country_lang(town.get("country"))[0],
                                                    "name": re.split(r"\s[•|(@\-–]", title)[0].strip()[:80], "bio": body[:600], "followers": None, "notes": f"találat / hit: {q}"})
                        if rec.get("followers") is None:
                            rec["followers"] = _followers(title + " " + body)
                        if rec.get("followers") is not None and rec["followers"] < MIN_FOLLOWERS:
                            seen.pop(key, None)
                    time.sleep(1.2)
    return list(seen.values())
