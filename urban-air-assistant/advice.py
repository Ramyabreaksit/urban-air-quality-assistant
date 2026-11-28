"""Personalised advice: input validation, impact estimates, rule-based plan, Gemini plan."""
from __future__ import annotations

import re

COMMUTES = ["Car", "Two-wheeler", "Bus / metro / train", "Walk / cycle", "Work from home"]
HOMES = ["Apartment", "Independent house"]
SENSITIVE = ["Young children", "Elderly members", "Asthma / breathing issues", "Pregnancy"]
COOKING = ["LPG / gas", "Induction / electric", "Wood / biomass"]

WORKING_DAYS_PER_MONTH = 22
MAX_COMMUTE_KM = 200.0
MAX_CITY_LENGTH = 60

# Rough, approximate tailpipe CO2 in kg per passenger-km. Estimates, not measurements.
CO2_PER_KM = {
    "Car": 0.17,
    "Two-wheeler": 0.04,
    "Bus / metro / train": 0.03,
    "Walk / cycle": 0.0,
    "Work from home": 0.0,
}


def sanitize_city(raw: str) -> str:
    """Keep letters, spaces, commas, dots, hyphens; cap length."""
    cleaned = re.sub(r"[^A-Za-z\u00C0-\u024F\u0900-\u0DFF ,.\-']", "", raw or "").strip()
    return cleaned[:MAX_CITY_LENGTH]


def commute_saving(current: str, alternative: str, km_one_way: float, days: int = WORKING_DAYS_PER_MONTH) -> dict:
    """Estimate monthly CO2 saved by switching commute mode (approximate)."""
    if current not in CO2_PER_KM or alternative not in CO2_PER_KM:
        raise ValueError("Unknown commute mode")
    km = max(0.0, min(float(km_one_way), MAX_COMMUTE_KM))
    monthly_km = km * 2 * days
    saved = (CO2_PER_KM[current] - CO2_PER_KM[alternative]) * monthly_km
    return {"monthly_km": round(monthly_km, 1), "co2_saved_kg": round(max(saved, 0.0), 1)}


def _routine_section(level: int, sensitive: bool) -> list[str]:
    """Daily routine advice for the given AQI level (0-5)."""
    lines = ["### Today's routine"]
    if level <= 1:
        lines.append("- Air is acceptable. Outdoor activity is fine; prefer morning or evening walks.")
    elif level == 2:
        lines.append("- Limit long outdoor exercise. Keep children and elders' outdoor time short.")
        if sensitive:
            lines.append("- Sensitive members should avoid outdoor play today.")
    else:
        lines.append("- Avoid outdoor exercise. Move play and workouts indoors.")
        lines.append("- Wear a well-fitted N95/FFP2 mask if you must go out; cloth masks do little for PM2.5.")
        lines.append("- Run errands at midday when air is usually a little cleaner than early morning smog.")
    return lines


def _indoor_section(home: str | None, cooking: str | None) -> list[str]:
    """Indoor air quality tips based on home type and cooking fuel."""
    lines = ["\n### Indoor air quality",
             "- Keep windows closed during peak pollution; air the home briefly when AQI dips.",
             "- Damp-mop and wipe surfaces instead of dry sweeping, which lifts dust."]
    if home == "Apartment":
        lines.append("- Seal door and window gaps with draught strips to cut outdoor air leaking in.")
    lines.append("- A HEPA purifier sized to the room helps most in the bedroom.")
    if cooking == "Wood / biomass":
        lines.append("- Cooking smoke is a major indoor source: use a chimney or exhaust and keep a window cracked while cooking.")
    else:
        lines.append("- Use the exhaust fan while cooking and avoid burning incense or mosquito coils indoors.")
    return lines


def _swaps_section(commute: str | None) -> list[str]:
    """Greener swap suggestions based on the current commute."""
    lines = ["\n### Greener swaps"]
    if commute in ("Car", "Two-wheeler"):
        lines.append("- Switch some trips to bus/metro/train, or carpool, to cut your own tailpipe emissions.")
    elif commute == "Bus / metro / train":
        lines.append("- Your commute is already low-emission. Walk the last stretch when AQI is below 100.")
    lines.append("- Avoid burning waste or leaves; report open burning near you.")
    return lines


def rule_based_plan(profile: dict, aq: dict) -> str:
    """Offline fallback plan so the app is useful without an AI key."""
    lines = (
        _routine_section(aq["level"], bool(profile.get("sensitive")))
        + _indoor_section(profile.get("home"), profile.get("cooking"))
        + _swaps_section(profile.get("commute"))
    )
    return "\n".join(lines)


def build_prompt(profile: dict, aq: dict, place: str, saving: dict | None) -> str:
    sens = ", ".join(profile.get("sensitive") or []) or "none stated"
    impact = (
        f"Estimated CO2 saved per month if they switch commute: {saving['co2_saved_kg']} kg "
        "(approximate)." if saving else "No commute switch estimate."
    )
    return f"""You are an urban air-quality assistant helping a family during smog season.
Use ONLY the data below. Do not invent AQI numbers. Be practical and concise.

Location: {place}
Live US AQI: {aq['aqi']} ({aq['category']}), PM2.5: {aq.get('pm2_5')} ug/m3, PM10: {aq.get('pm10')} ug/m3
Household: home type={profile.get('home')}, commute={profile.get('commute')}, cooking={profile.get('cooking')}, sensitive members={sens}
{impact}

Write markdown with exactly these sections:
### Today's routine  (3-4 low-emission daily actions tailored to the household)
### Indoor air quality hacks  (3-4 tips)
### Sustainable alternatives  (2-3 swaps for their commute/cooking)
### Why this helps  (explain the direct impact of each suggestion in plain language, with the CO2 estimate if given)
Add one line: this is general guidance, not medical advice."""


def gemini_plan(prompt: str, api_key: str, model: str = "gemini-2.5-flash") -> str:
    """Call Gemini. Raises on failure so the caller can fall back."""
    from google import genai  # imported lazily so tests run without the SDK/key

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=model, contents=prompt)
    text = (resp.text or "").strip()
    if not text:
        raise RuntimeError("Empty response from Gemini")
    return text
