"""Szótárak: kategóriák, pszichográfiai címkék, közönség-szegmensek, célcsoport-előbeállítások. HU/EN."""
from __future__ import annotations

PLATFORMS = ["instagram", "tiktok", "youtube", "facebook", "x", "linkedin", "twitch"]

# Tartalmi kategória / niche
CATEGORIES = {
    "lifestyle": ("Lifestyle", "Lifestyle"), "fashion": ("Divat", "Fashion"), "beauty": ("Szépség", "Beauty"),
    "fitness": ("Fitnesz és sport", "Fitness & sport"), "health": ("Egészség, wellness", "Health & wellness"),
    "food": ("Gasztro", "Food"), "travel": ("Utazás", "Travel"), "tech": ("Tech, gadget", "Tech & gadgets"),
    "gaming": ("Gaming, e-sport", "Gaming & e-sports"), "family": ("Család, szülőség", "Family & parenting"),
    "business": ("Üzlet, karrier, KKV", "Business & career"), "finance": ("Pénzügy", "Personal finance"),
    "education": ("Oktatás, tudomány", "Education & science"), "music": ("Zene", "Music"),
    "entertainment": ("Szórakozás, humor", "Entertainment & comedy"), "art": ("Művészet, design", "Art & design"),
    "home": ("Otthon, lakberendezés", "Home & interior"), "auto": ("Autó, motor", "Cars & motors"),
    "outdoor": ("Természet, outdoor", "Nature & outdoor"), "pets": ("Kisállat", "Pets"),
    "local": ("Helyi közélet, városi élet", "Local life & community"), "sustainability": ("Fenntarthatóság", "Sustainability"),
}

# Pszichográfia – érdeklődés
INTERESTS = {
    "sport": ("Sport", "Sport"), "gaming": ("Gaming", "Gaming"), "tech": ("Technológia", "Technology"),
    "fashion": ("Divat", "Fashion"), "beauty": ("Szépségápolás", "Beauty"), "food": ("Gasztronómia", "Food"),
    "travel": ("Utazás", "Travel"), "music": ("Zene", "Music"), "film": ("Film, sorozat", "Film & series"),
    "reading": ("Olvasás", "Reading"), "nature": ("Természet", "Nature"), "diy": ("Barkácsolás, kreatív", "DIY & crafts"),
    "cars": ("Autók", "Cars"), "finance": ("Befektetés, pénzügy", "Investing & finance"), "career": ("Karrier", "Career"),
    "parenting": ("Gyereknevelés", "Parenting"), "pets": ("Kisállatok", "Pets"), "nightlife": ("Éjszakai élet", "Nightlife"),
    "wellness": ("Wellness, mentális egészség", "Wellness & mental health"), "photography": ("Fotózás", "Photography"),
}
# Pszichográfia – értékek
VALUES = {
    "family": ("Család", "Family"), "achievement": ("Teljesítmény, siker", "Achievement"), "adventure": ("Kaland", "Adventure"),
    "security": ("Biztonság", "Security"), "sustainability": ("Környezettudatosság", "Sustainability"),
    "community": ("Közösség, lokálpatriotizmus", "Community & local pride"), "creativity": ("Kreativitás", "Creativity"),
    "health": ("Egészség", "Health"), "tradition": ("Hagyomány", "Tradition"), "independence": ("Függetlenség", "Independence"),
    "status": ("Státusz, luxus", "Status & luxury"), "frugality": ("Takarékosság, ár-érték", "Frugality & value"),
    "authenticity": ("Hitelesség", "Authenticity"), "fun": ("Szórakozás", "Fun"), "learning": ("Tanulás, fejlődés", "Learning"),
}
# Pszichográfia – életstílus
LIFESTYLES = {
    "urban": ("Nagyvárosi", "Urban"), "small_town": ("Kisvárosi, vidéki", "Small-town / rural"), "student": ("Egyetemista", "Student"),
    "young_professional": ("Fiatal karrierista", "Young professional"), "parent": ("Kisgyerekes szülő", "Parent of young kids"),
    "entrepreneur": ("Vállalkozó", "Entrepreneur"), "athlete": ("Sportos, aktív", "Active / athlete"),
    "homebody": ("Otthonülő, cozy", "Homebody"), "traveler": ("Digitális nomád, utazó", "Traveler / nomad"),
    "premium": ("Prémium fogyasztó", "Premium consumer"), "budget": ("Árérzékeny", "Budget-conscious"),
    "early_adopter": ("Early adopter, tech-savvy", "Early adopter"), "eco": ("Zöld, tudatos", "Eco-conscious"),
    "gamer": ("Gamer", "Gamer"), "senior_active": ("Aktív 50+", "Active 50+"),
}
# Hangnem / személyiség
TONES = {
    "humorous": ("Humoros", "Humorous"), "inspirational": ("Inspiráló", "Inspirational"), "educational": ("Edukáló", "Educational"),
    "authentic": ("Őszinte, hétköznapi", "Authentic / relatable"), "aesthetic": ("Esztétikus, kurált", "Aesthetic / curated"),
    "provocative": ("Provokatív", "Provocative"), "calm": ("Nyugodt, minimalista", "Calm / minimal"),
    "energetic": ("Energikus", "Energetic"), "professional": ("Szakmai", "Professional"), "storyteller": ("Történetmesélő", "Storyteller"),
}

AGE_BUCKETS = ["13-17", "18-24", "25-34", "35-44", "45-54", "55+"]
GENDERS = {"female": ("Nő", "Female"), "male": ("Férfi", "Male"), "other": ("Egyéb / pár / csapat", "Other / duo / team")}
TIERS = {  # követőszám alapú kategóriák
    "nano": (1_000, 10_000), "micro": (10_000, 50_000), "mid": (50_000, 200_000), "macro": (200_000, 1_000_000), "mega": (1_000_000, 10**9),
}

# Célcsoport-előbeállítások: egy klikkel több szűrő. Kulcsok = a /api/search paraméterei.
TARGET_GROUPS = {
    "genz": {"label": ("Z generáció (18–24)", "Gen Z (18–24)"),
             "filters": {"aud_age": "18-24", "aud_age_min": 35, "platform": ["tiktok", "instagram", "youtube"]}},
    "young_adults": {"label": ("Fiatal felnőttek (25–34)", "Young adults (25–34)"),
                     "filters": {"aud_age": "25-34", "aud_age_min": 35}},
    "families": {"label": ("Kisgyerekes családok", "Families with young kids"),
                 "filters": {"categories": ["family"], "lifestyles": ["parent"], "aud_age": "25-34", "aud_age_min": 25}},
    "students": {"label": ("Egyetemisták, diákok", "Students"),
                 "filters": {"lifestyles": ["student"], "aud_age": "18-24", "aud_age_min": 40}},
    "fitness": {"label": ("Sportos, egészségtudatos", "Fitness & health-conscious"),
                "filters": {"categories": ["fitness", "health"], "values": ["health"]}},
    "gamers": {"label": ("Gamerek, tech-rajongók", "Gamers & tech fans"),
               "filters": {"categories": ["gaming", "tech"], "aud_gender": "male", "aud_gender_min": 50}},
    "women_25_44": {"label": ("Nők 25–44", "Women 25–44"),
                    "filters": {"aud_gender": "female", "aud_gender_min": 60, "aud_age": "25-34", "aud_age_min": 25}},
    "premium": {"label": ("Prémium, státuszorientált", "Premium / status-driven"),
                "filters": {"lifestyles": ["premium"], "values": ["status"]}},
    "value_seekers": {"label": ("Árérzékeny, ár-érték keresők", "Value seekers"),
                      "filters": {"lifestyles": ["budget"], "values": ["frugality"]}},
    "smb": {"label": ("KKV, vállalkozók, üzleti döntéshozók", "SMB owners & business decision-makers"),
            "filters": {"categories": ["business", "finance"], "lifestyles": ["entrepreneur"], "platform": ["linkedin", "instagram", "youtube", "facebook"]}},
    "early_adopters": {"label": ("Early adopterek, mobil- és gadget-rajongók", "Early adopters & gadget fans"),
                       "filters": {"categories": ["tech"], "lifestyles": ["early_adopter"]}},
    "local_community": {"label": ("Lokálpatrióta, helyi közösség", "Local community"),
                        "filters": {"categories": ["local"], "values": ["community"], "aud_loc_min": 40}},
    "eco": {"label": ("Zöld, fenntarthatóságra nyitott", "Eco-conscious"),
            "filters": {"categories": ["sustainability"], "values": ["sustainability"], "lifestyles": ["eco"]}},
    "active_50": {"label": ("Aktív 45+", "Active 45+"),
                  "filters": {"aud_age": "45-54", "aud_age_min": 25, "lifestyles": ["senior_active"]}},
}


def label(table: dict, key: str, lang: str = "hu") -> str:
    v = table.get(key)
    if not v:
        return key
    return v[0] if lang == "hu" else v[1]


def as_options(table: dict, lang: str = "hu") -> list[dict]:
    return [{"key": k, "label": label(table, k, lang)} for k in table]
