"""Urban Air Quality Assistant - Streamlit app."""
import logging

import streamlit as st

from advice import (COMMUTES, COOKING, HOMES, SENSITIVE, build_prompt, commute_saving,
                    gemini_plan, rule_based_plan, sanitize_city)
from aqi import AirQualityError, fetch_air_quality, geocode

logger = logging.getLogger(__name__)

st.set_page_config(page_title="Urban Air Quality Assistant", page_icon="🌫️", layout="centered")


@st.cache_data(ttl=600, show_spinner=False)
def cached_air(city: str):
    place = geocode(city)
    return place, fetch_air_quality(place["lat"], place["lon"])


@st.cache_data(ttl=600, show_spinner=False)
def cached_plan(prompt: str, key: str) -> str:
    """Cache Gemini output so identical inputs do not trigger a new API call."""
    return gemini_plan(prompt, key)


def api_key() -> str | None:
    try:
        return st.secrets["GEMINI_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None


def render_form() -> dict | None:
    """Show the input form; return the answers when submitted."""
    with st.form("profile"):
        city = st.text_input(
            "Your city",
            placeholder="e.g. Chennai, Delhi, Lahore",
            max_chars=60,
            help="Type the name of your city. Live air quality is fetched for it.",
        )
        c1, c2 = st.columns(2)
        home = c1.selectbox("Home type", HOMES, help="Apartment or independent house.")
        cooking = c2.selectbox("Cooking fuel", COOKING, help="What you mainly cook with.")
        commute = st.selectbox("Main commute", COMMUTES, help="How you usually travel to work or school.")
        km = st.slider("One-way commute distance (km)", 0, 60, 10,
                       help="Used to estimate monthly CO2 savings.")
        sensitive = st.multiselect(
            "Anyone in the household who is more sensitive?", SENSITIVE,
            help="Children, elders, pregnancy or breathing issues get stricter advice.")
        alt = st.selectbox("Cleaner commute you could try",
                           [m for m in COMMUTES if m != commute],
                           help="We compare this with your current commute.")
        submitted = st.form_submit_button("Get my plan")
    if not submitted:
        return None
    return {"city": sanitize_city(city), "home": home, "cooking": cooking,
            "commute": commute, "km": km, "sensitive": sensitive, "alt": alt}


def render_air(place: dict, aq: dict) -> None:
    st.subheader(place["name"])
    m1, m2, m3 = st.columns(3)
    m1.metric("US AQI", aq["aqi"])
    m2.metric("PM2.5 (µg/m³)", aq["pm2_5"])
    m3.metric("PM10 (µg/m³)", aq["pm10"])
    # Text status (not colour alone) announced politely by screen readers.
    st.markdown(
        f'<div role="status" aria-live="polite">Air quality in {place["name"]} is '
        f'<strong>{aq["category"]}</strong> (AQI {aq["aqi"]}, level {aq["level"]} of 5).</div>',
        unsafe_allow_html=True,
    )


def render_plan(answers: dict, place: dict, aq: dict) -> None:
    profile = {k: answers[k] for k in ("home", "cooking", "commute", "sensitive")}
    saving = commute_saving(answers["commute"], answers["alt"], answers["km"]) if answers["km"] else None
    if saving and saving["co2_saved_kg"] > 0:
        st.info(f"Switching from {answers['commute']} to {answers['alt']} could save about "
                f"**{saving['co2_saved_kg']} kg CO₂/month** (rough estimate).")

    key = api_key()
    plan = None
    if key:
        try:
            with st.spinner("Personalising with Gemini..."):
                plan = cached_plan(build_prompt(profile, aq, place["name"], saving), key)
        except Exception:  # SDK raises several error types; any failure falls back safely
            logger.exception("Gemini request failed")
            st.warning("AI advice is unavailable right now, showing the standard plan.")
    st.markdown(plan or rule_based_plan(profile, aq))
    st.caption("General guidance, not medical advice. Data: Open-Meteo air-quality API.")


def main() -> None:
    st.title("🌫️ Urban Air Quality Assistant")
    st.write("Get a smog-season plan for your family, based on live air quality in your city.")
    answers = render_form()
    if answers is None:
        return
    if not answers["city"]:
        st.error("Please enter a city name.")
        return
    try:
        with st.spinner("Fetching live air quality..."):
            place, aq = cached_air(answers["city"])
    except AirQualityError as exc:
        st.error(str(exc))
        return
    render_air(place, aq)
    render_plan(answers, place, aq)


main()
