"""Szintetikus DEMO-adathalmaz a szűrők kipróbálásához. Minden rekord source='demo', handle *_demo – NEM valós személyek."""
from __future__ import annotations

import random

from . import geo
from .taxonomy import CATEGORIES, INTERESTS, LIFESTYLES, PLATFORMS, TONES, VALUES

FIRST_F = ["Anna", "Réka", "Zsófi", "Lilla", "Dóra", "Boglárka", "Vivien", "Petra", "Kata", "Eszter", "Nóra", "Fanni", "Luca", "Emese", "Hanna"]
FIRST_M = ["Bence", "Máté", "Ádám", "Dani", "Levente", "Gergő", "Marci", "Zoli", "Balázs", "Kristóf", "Tamás", "Áron", "Barni", "Dávid", "Peti"]
LAST = ["Kovács", "Nagy", "Szabó", "Tóth", "Horváth", "Varga", "Kiss", "Molnár", "Németh", "Farkas", "Balogh", "Papp", "Takács", "Juhász", "Lakatos", "Mészáros"]

# kategória → jellemző pszichográfia / közönség
PROFILE = {
    "fitness": dict(i=["sport", "wellness", "food"], v=["health", "achievement"], l=["athlete", "young_professional"], t=["energetic", "inspirational"], age=("25-34", 40), g=("female", 55)),
    "beauty": dict(i=["beauty", "fashion"], v=["authenticity", "status"], l=["urban", "premium"], t=["aesthetic", "authentic"], age=("18-24", 45), g=("female", 85)),
    "fashion": dict(i=["fashion", "photography"], v=["status", "creativity"], l=["urban", "premium"], t=["aesthetic"], age=("18-24", 40), g=("female", 75)),
    "food": dict(i=["food", "travel"], v=["tradition", "fun"], l=["urban", "homebody"], t=["storyteller", "authentic"], age=("25-34", 38), g=("female", 60)),
    "travel": dict(i=["travel", "photography", "nature"], v=["adventure", "independence"], l=["traveler"], t=["inspirational", "aesthetic"], age=("25-34", 42), g=("female", 55)),
    "tech": dict(i=["tech", "gaming", "finance"], v=["learning", "independence"], l=["early_adopter", "young_professional"], t=["educational", "professional"], age=("25-34", 40), g=("male", 75)),
    "gaming": dict(i=["gaming", "tech", "film"], v=["fun", "community"], l=["gamer", "student"], t=["humorous", "energetic"], age=("18-24", 50), g=("male", 80)),
    "family": dict(i=["parenting", "food", "diy"], v=["family", "security"], l=["parent", "small_town"], t=["authentic", "storyteller"], age=("25-34", 45), g=("female", 80)),
    "business": dict(i=["career", "finance", "reading"], v=["achievement", "independence"], l=["entrepreneur", "young_professional"], t=["professional", "educational"], age=("35-44", 38), g=("male", 60)),
    "finance": dict(i=["finance", "career"], v=["security", "frugality", "learning"], l=["young_professional", "budget"], t=["educational"], age=("25-34", 45), g=("male", 65)),
    "education": dict(i=["reading", "tech"], v=["learning", "authenticity"], l=["student", "urban"], t=["educational", "calm"], age=("18-24", 40), g=("female", 55)),
    "music": dict(i=["music", "nightlife", "film"], v=["creativity", "fun"], l=["urban", "student"], t=["energetic"], age=("18-24", 48), g=("female", 52)),
    "entertainment": dict(i=["film", "music", "gaming"], v=["fun", "authenticity"], l=["student", "urban"], t=["humorous", "provocative"], age=("18-24", 50), g=("male", 55)),
    "art": dict(i=["photography", "diy", "reading"], v=["creativity", "authenticity"], l=["urban"], t=["aesthetic", "calm"], age=("25-34", 40), g=("female", 62)),
    "home": dict(i=["diy", "food"], v=["family", "frugality"], l=["parent", "homebody", "small_town"], t=["calm", "aesthetic"], age=("35-44", 38), g=("female", 85)),
    "auto": dict(i=["cars", "tech", "sport"], v=["status", "adventure"], l=["premium", "small_town"], t=["energetic", "educational"], age=("25-34", 40), g=("male", 88)),
    "outdoor": dict(i=["nature", "sport", "travel"], v=["adventure", "sustainability", "health"], l=["athlete", "eco"], t=["calm", "inspirational"], age=("35-44", 35), g=("male", 55)),
    "pets": dict(i=["pets", "nature"], v=["family", "fun"], l=["homebody", "small_town"], t=["humorous", "authentic"], age=("25-34", 38), g=("female", 70)),
    "local": dict(i=["food", "nature", "photography"], v=["community", "tradition"], l=["small_town", "urban"], t=["storyteller", "authentic"], age=("35-44", 35), g=("female", 55)),
    "sustainability": dict(i=["nature", "diy", "food"], v=["sustainability", "frugality"], l=["eco", "budget"], t=["educational", "calm"], age=("25-34", 45), g=("female", 68)),
    "health": dict(i=["wellness", "food", "sport"], v=["health", "family"], l=["parent", "senior_active"], t=["calm", "educational"], age=("45-54", 30), g=("female", 70)),
    "lifestyle": dict(i=["fashion", "travel", "food"], v=["fun", "authenticity"], l=["urban", "young_professional"], t=["aesthetic", "authentic"], age=("25-34", 40), g=("female", 65)),
}

BIO = {
    "hu": "{cat} tartalmak {city}ből és környékéről. {extra} Együttműködés: DM 📩",
}
EXTRA = ["Minden nap új sztori.", "Őszintén, szűrő nélkül.", "Helyi tippek és kedvencek.", "Heti vlog vasárnap.", "Kérdezz bátran!", "Podcast is van 🎙️"]


def _dist(main: str, main_share: int, buckets: list[str], rnd: random.Random) -> dict[str, float]:
    rest = [b for b in buckets if b != main]
    remaining = 100 - main_share
    weights = [rnd.random() + 0.2 for _ in rest]
    tot = sum(weights)
    d = {main: float(main_share)}
    for b, w in zip(rest, weights):
        d[b] = round(remaining * w / tot, 1)
    return d


FIRST_EU_F = ["Anna", "Emma", "Sofia", "Lena", "Julia", "Laura", "Marie", "Elena", "Nina", "Clara", "Zoe", "Mia", "Eva", "Sara", "Lucia"]
FIRST_EU_M = ["Luca", "Max", "Leon", "Noah", "Jan", "Tomas", "Marco", "Paul", "David", "Jonas", "Felix", "Adam", "Nico", "Oscar", "Milan"]
LAST_EU = ["Müller", "Novak", "Rossi", "Garcia", "Martin", "Kowalski", "Bauer", "Dubois", "Jensen", "Horvat", "Popescu", "Silva", "Berg", "Fischer", "Costa", "Weber"]


def generate_for_towns(towns: list[dict], per_town: int = 12, seed: int | None = None, collection_id: int | None = None) -> list[dict]:
    """Szintetikus profilok tetszőleges (európai) városlistára – a gyűjtés körzetében a szűrők kipróbálásához."""
    rnd = random.Random(seed if seed is not None else len(towns) * 7919)
    recs = []
    for town in towns:
        n = max(3, int(per_town * min(2.5, max(0.4, (town.get("population") or 20000) / 80000) ** 0.5)))
        hu = (town.get("country") or "") == "hu"
        lang = geo.country_lang(town.get("country"))[0]
        for _ in range(n):
            cat = rnd.choice(list(PROFILE))
            p = PROFILE[cat]
            gender = "female" if rnd.random() < (0.6 if p["g"][0] == "female" else 0.35) else "male"
            first = rnd.choice((FIRST_F if hu else FIRST_EU_F) if gender == "female" else (FIRST_M if hu else FIRST_EU_M))
            last = rnd.choice(LAST if hu else LAST_EU)
            handle = f"{geo.norm(first)}.{geo.norm(last)}{rnd.randint(1, 999)}_demo"
            platform = rnd.choices(["instagram", "tiktok", "youtube", "facebook", "linkedin"], [45, 25, 15, 8, 4 if cat in ("business", "finance", "tech") else 1])[0]
            followers = int(10 ** rnd.uniform(3.2, 5.6 + min(0.7, (town.get("population") or 0) / 1_500_000)))
            er = round(max(0.4, 12 * followers ** -0.18 + rnd.uniform(-1, 1.5)), 2)
            aud_age = _dist(p["age"][0], max(15, p["age"][1] + rnd.randint(-8, 8)), ["13-17", "18-24", "25-34", "35-44", "45-54", "55+"], rnd)
            g_main, g_share = p["g"]
            g_share = max(20, min(95, g_share + rnd.randint(-10, 10)))
            aud_gender = {g_main: float(g_share), ("male" if g_main == "female" else "female"): round(100 - g_share - 1.5, 1), "other": 1.5}
            local_share = rnd.randint(20, 65)
            aud_loc = {town["name"]: float(local_share), "egyéb / other": round(100.0 - local_share, 1)}
            cat_label = CATEGORIES[cat][0 if hu else 1].split(",")[0]
            bio = (f"{cat_label} tartalmak {town['name']}ből és környékéről. Együttműködés: DM 📩" if hu
                   else f"{cat_label} content from {town['name']} and around. Collabs: DM 📩")
            recs.append({"platform": platform, "handle": handle, "name": f"{first} {last}", "city": town["name"], "county": town.get("county") or "",
                         "country": town.get("country"), "lat": town["lat"], "lon": town["lon"], "bio": bio, "followers": followers, "engagement_rate": er,
                         "avg_views": int(followers * rnd.uniform(0.08, 0.6)), "posts_per_week": round(rnd.uniform(1, 10), 1), "language": lang,
                         "gender": gender, "age": rnd.randint(19, 45), "categories": [cat] + rnd.sample([c for c in CATEGORIES if c != cat], rnd.randint(0, 2)),
                         "interests": p["i"] + rnd.sample(list(INTERESTS), 1), "values": p["v"] + rnd.sample(list(VALUES), 1), "lifestyles": p["l"],
                         "tones": p["t"] + rnd.sample(list(TONES), 1), "audience_age": aud_age, "audience_gender": aud_gender, "audience_locations": aud_loc,
                         "audience_interests": rnd.sample(p["i"] + list(INTERESTS), 4), "audience_language": lang, "contact_email": f"{handle}@example.invalid",
                         "price_estimate_huf": int(followers * rnd.uniform(6, 25) // 1000 * 1000), "verified": followers > 150_000 and rnd.random() < 0.6,
                         "source": "demo", "enriched": 1, "collection_id": collection_id, "notes": "SZINTETIKUS DEMO – nem valós személy / synthetic, not a real person"})
    return recs


def generate(n: int = 600, seed: int = 42) -> list[dict]:
    rnd = random.Random(seed)
    towns = geo.settlements()
    weights = [max(s["population"], 5000) ** 0.6 for s in towns]
    recs = []
    used = set()
    for _ in range(n):
        town = rnd.choices(towns, weights)[0]
        cat = rnd.choice(list(PROFILE))
        p = PROFILE[cat]
        gender = "female" if rnd.random() < (0.6 if p["g"][0] == "female" else 0.35) else "male"
        first = rnd.choice(FIRST_F if gender == "female" else FIRST_M)
        last = rnd.choice(LAST)
        handle = f"{geo.norm(first)}.{geo.norm(last)}{rnd.randint(1, 99)}_demo"
        if handle in used:
            continue
        used.add(handle)
        platform = rnd.choices(["instagram", "tiktok", "youtube", "facebook", "linkedin", "twitch"],
                               [45, 25, 15, 8, 4 if cat in ("business", "finance", "tech") else 1, 3 if cat == "gaming" else 0.3])[0]
        followers = int(10 ** rnd.uniform(3.2, 5.9)) if town["population"] < 100_000 else int(10 ** rnd.uniform(3.4, 6.3))
        er = round(max(0.4, 12 * followers ** -0.18 + rnd.uniform(-1, 1.5)), 2)
        age = rnd.randint(19, 45)
        cats = [cat] + rnd.sample([c for c in CATEGORIES if c != cat], rnd.randint(0, 2))
        aud_age = _dist(p["age"][0], p["age"][1] + rnd.randint(-8, 8), ["13-17", "18-24", "25-34", "35-44", "45-54", "55+"], rnd)
        g_main, g_share = p["g"]
        g_share = max(20, min(95, g_share + rnd.randint(-10, 10)))
        aud_gender = {g_main: float(g_share), ("male" if g_main == "female" else "female"): round(100 - g_share - 1.5, 1), "other": 1.5}
        local_share = rnd.randint(25, 70) if cat == "local" or town["population"] < 60_000 else rnd.randint(10, 45)
        nearby = [s for s in geo.settlements_within(town["lat"], town["lon"], 80) if s["name"] != town["name"]][:3]
        aud_loc = {town["name"]: float(local_share), "Budapest": float(rnd.randint(8, 30)) if town["name"] != "Budapest" else 0.0}
        for s in nearby:
            aud_loc[s["name"]] = float(rnd.randint(2, 8))
        aud_loc = {k: v for k, v in aud_loc.items() if v > 0}
        aud_loc["egyéb"] = round(max(0.0, 100 - sum(aud_loc.values())), 1)
        cat_hu = CATEGORIES[cat][0].split(",")[0].lower()
        recs.append({
            "platform": platform, "handle": handle, "name": f"{first} {last}", "city": town["name"], "country": "hu", "lat": town["lat"], "lon": town["lon"],
            "bio": BIO["hu"].format(cat=cat_hu.capitalize(), city=town["name"], extra=rnd.choice(EXTRA)),
            "followers": followers, "engagement_rate": er, "avg_views": int(followers * rnd.uniform(0.08, 0.6)),
            "posts_per_week": round(rnd.uniform(1, 10), 1), "language": "hu", "gender": gender, "age": age,
            "categories": cats, "interests": p["i"] + rnd.sample(list(INTERESTS), 1), "values": p["v"] + rnd.sample(list(VALUES), 1),
            "lifestyles": p["l"], "tones": p["t"] + rnd.sample(list(TONES), 1),
            "audience_age": aud_age, "audience_gender": aud_gender, "audience_locations": aud_loc,
            "audience_interests": rnd.sample(p["i"] + list(INTERESTS), 4), "audience_language": "hu",
            "contact_email": f"{handle}@example.invalid", "price_estimate_huf": int(followers * rnd.uniform(6, 25) // 1000 * 1000),
            "verified": followers > 150_000 and rnd.random() < 0.6, "source": "demo", "enriched": 1,
            "notes": "SZINTETIKUS DEMO – nem valós személy",
        })
    return recs
