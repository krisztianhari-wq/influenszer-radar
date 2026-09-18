"""LLM-dúsítás: bio + snippet → kategória, pszichográfia, becsült közönség. Háttér: claude-api → claude-cli → ollama → rules.
Minden LLM-becslés `notes`-ban jelölve; közönség-számok csak akkor, ha a bemenetben szerepelnek."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from typing import Any

from .taxonomy import AGE_BUCKETS, CATEGORIES, INTERESTS, LIFESTYLES, TONES, VALUES

MODEL = os.environ.get("RADAR_MODEL", "claude-opus-5")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")

SYSTEM = ("Influenszer-profilokat címkézel marketing-célcsoport-elemzéshez. A bemenet: platform, handle, név, város, bio/snippet. "
          "Csak a megadott szótárak kulcsaival válaszolj, szigorúan JSON-ban, magyarázat nélkül. Ha valami nem derül ki, hagyd üresen. "
          "Ne találj ki követőszámot vagy közönség-százalékot; a közönség életkor/nem mezőt csak durva, a tartalomból következő becslésként add meg "
          "(pl. {'18-24': 45} = a bio alapján főleg fiatal közönség), és jelöld estimated=true-val.\n"
          f"categories: {list(CATEGORIES)}\ninterests: {list(INTERESTS)}\nvalues: {list(VALUES)}\nlifestyles: {list(LIFESTYLES)}\ntones: {list(TONES)}\n"
          f"age buckets: {AGE_BUCKETS}; gender: female|male|other\n"
          'Kimenet: {"categories":[],"interests":[],"values":[],"lifestyles":[],"tones":[],"gender":null,"language":"hu",'
          '"audience_age":{},"audience_gender":{},"audience_interests":[],"estimated":true,"summary":"1 mondat magyarul"}')


def _claude_cli() -> str | None:
    return shutil.which("claude") or (os.path.expanduser("~/.local/bin/claude") if os.path.exists(os.path.expanduser("~/.local/bin/claude")) else None)


def _api_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")) or os.path.isdir(os.path.expanduser("~/.config/anthropic"))


def _ollama_up() -> bool:
    try:
        import urllib.request
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def backends() -> list[str]:
    forced = os.environ.get("RADAR_LLM")
    if forced:
        return [forced]
    out = []
    if _api_available():
        out.append("api")
    if _claude_cli():
        out.append("cli")
    if _ollama_up():
        out.append("ollama")
    return out + ["rules"]


def _prompt(rec: dict) -> str:
    slim = {k: rec.get(k) for k in ("platform", "handle", "name", "city", "bio", "notes", "followers")}
    return "Címkézd ezt a profilt:\n" + json.dumps(slim, ensure_ascii=False)


def _claude_api(rec: dict) -> str:
    import anthropic
    client = anthropic.Anthropic()
    kwargs: dict[str, Any] = dict(model=MODEL, max_tokens=2000, system=SYSTEM, messages=[{"role": "user", "content": _prompt(rec)}],
                                  thinking={"type": "adaptive"}, output_config={"effort": "low"})
    try:
        msg = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    except TypeError:
        msg = client.messages.create(**kwargs)
    if getattr(msg, "stop_reason", None) == "refusal":
        raise RuntimeError("refusal")
    return "\n".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _claude_cli_run(rec: dict) -> str:
    exe = _claude_cli()
    p = subprocess.run([exe, "-p", "--output-format", "text", "--append-system-prompt", SYSTEM + " Do not use tools."], input=_prompt(rec),
                       capture_output=True, text=True, timeout=300, env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    if p.returncode != 0 or not p.stdout.strip():
        raise RuntimeError((p.stderr or p.stdout)[-200:])
    return p.stdout


def _ollama(rec: dict) -> str:
    import urllib.request
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=json.dumps({"model": OLLAMA_MODEL, "stream": False, "format": "json",
                                 "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _prompt(rec)}]}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())["message"]["content"]


KEYWORDS = {  # szabályalapú tartalék
    "fitness": ["fitnesz", "edz", "gym", "futás", "crossfit", "workout", "sport"], "beauty": ["smink", "makeup", "szépség", "köröm", "haj", "skincare"],
    "fashion": ["divat", "outfit", "fashion", "ootd", "stílus"], "food": ["gasztro", "recept", "food", "étterem", "sütés", "főzés"],
    "travel": ["utaz", "travel", "kaland", "nomád"], "tech": ["tech", "gadget", "mobil", "okostelefon", "applikáció", "ai"],
    "gaming": ["gamer", "gaming", "stream", "twitch", "e-sport", "esport"], "family": ["anya", "apa", "baba", "kisgyerek", "család", "szülő"],
    "business": ["vállalkoz", "üzlet", "kkv", "startup", "marketing", "karrier"], "finance": ["pénzügy", "befektet", "megtakarít", "tőzsde"],
    "education": ["oktatás", "tanul", "tudomány", "egyetem"], "music": ["zene", "dj", "zenész", "koncert"],
    "entertainment": ["humor", "vicc", "szórakoz", "comedy", "paródia"], "art": ["művész", "design", "grafik", "fotó", "illusztr"],
    "home": ["lakber", "otthon", "kert", "diy"], "auto": ["autó", "motor", "tuning"], "outdoor": ["túra", "hegy", "kemping", "természet", "horgász"],
    "pets": ["kutya", "macska", "kisállat"], "local": ["helyi", "város", "közösség", "programok"], "sustainability": ["fenntartható", "zöld", "öko", "zero waste"],
    "health": ["egészség", "wellness", "mentál", "jóga", "meditáció"],
}


def _rules(rec: dict) -> dict:
    text = " ".join(str(rec.get(k) or "") for k in ("bio", "name", "notes")).lower()
    cats = [c for c, kws in KEYWORDS.items() if any(k in text for k in kws)] or ["lifestyle"]
    return {"categories": cats[:3], "interests": [], "values": [], "lifestyles": [], "tones": [], "estimated": True,
            "summary": "Szabályalapú címkézés kulcsszavak alapján (LLM nélkül)."}


def _parse(txt: str) -> dict:
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else {}


def enrich(rec: dict) -> tuple[dict, str]:
    """→ (mezők a rekordhoz, háttér neve)."""
    for b in backends():
        try:
            if b == "api":
                data, name = _parse(_claude_api(rec)), "claude-api"
            elif b == "cli":
                data, name = _parse(_claude_cli_run(rec)), "claude-cli"
            elif b == "ollama":
                data, name = _parse(_ollama(rec)), f"ollama:{OLLAMA_MODEL}"
            else:
                data, name = _rules(rec), "rules"
            if not data:
                continue
            return _clean(data, name), name
        except Exception:  # noqa: BLE001
            continue
    return _clean(_rules(rec), "rules"), "rules"


def _clean(d: dict, backend: str) -> dict:
    def keep(lst, table):
        return [x for x in (lst or []) if x in table]
    out: dict[str, Any] = {"categories": keep(d.get("categories"), CATEGORIES), "interests": keep(d.get("interests"), INTERESTS),
                           "values": keep(d.get("values"), VALUES), "lifestyles": keep(d.get("lifestyles"), LIFESTYLES),
                           "tones": keep(d.get("tones"), TONES), "audience_interests": keep(d.get("audience_interests"), INTERESTS), "enriched": 1}
    if d.get("gender") in ("female", "male", "other"):
        out["gender"] = d["gender"]
    if d.get("language"):
        out["language"] = str(d["language"])[:5].lower()
    aa = {k: float(v) for k, v in (d.get("audience_age") or {}).items() if k in AGE_BUCKETS}
    ag = {k: float(v) for k, v in (d.get("audience_gender") or {}).items() if k in ("female", "male", "other")}
    if aa:
        out["audience_age"] = aa
    if ag:
        out["audience_gender"] = ag
    tag = f"[{backend}{' · becslés' if d.get('estimated', True) else ''}] {d.get('summary', '')}".strip()
    out["notes"] = tag
    return out
