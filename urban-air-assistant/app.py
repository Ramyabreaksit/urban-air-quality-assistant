"""Urban Air Quality Assistant - Streamlit app."""
import streamlit as st

from advice import (COMMUTES, COOKING, HOMES, SENSITIVE, build_prompt, commute_saving,
                    gemini_plan, rule_based_plan, sanitize_city)
from aqi import AirQualityError, fetch_air_quality, geocode

st.set_page_config(page_title="Urban Air Quality Assistant", page_icon="🌫️", layout="centered")


@st.cache_data(ttl=600, show_spinner=False)
def cached_air(city: str):
    place = geocode(city)
    return place, fetch_air_quality(place["lat"], place["lon"])


def api_key() -> str | None:
    try:
                return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None


st.title("🌫️ Urban Air Quality Assistant")
st.write("Get a smog-season plan for your family, based on live air quality in your city.")

with st.form("profile"):
    city = st.text_input("Your city", placeholder="e.g. Chennai, Delhi, Lahore", max_chars=60)
    c1, c2 = st.columns(2)
    home = c1.selectbox("Home type", HOMES)
    cooking = c2.selectbox("Cooking fuel", COOKING)
    commute = st.selectbox("Main commute", COMMUTES)
    km = st.slider("One-way commute distance (km)", 0, 60, 10)
    sensitive = st.multiselect("Anyone in the household who is more sensitive?", SENSITIVE)
    alt = st.selectbox("Cleaner commute you could try", [m for m in COMMUTES if m != commute])
    submitted = st.form_submit_button("Get my plan")

if submitted:
    city = sanitize_city(city)
    if not city:
        st.error("Please enter a city name.")
        st.stop()
    try:
        with st.spinner("Fetching live air quality..."):
            place, aq = cached_air(city)
    except AirQualityError as exc:
        st.error(str(exc))
        st.stop()

    st.subheader(place["name"])
    m1, m2, m3 = st.columns(3)
    m1.metric("US AQI", aq["aqi"])
    m2.metric("PM2.5 (µg/m³)", aq["pm2_5"])
    m3.metric("PM10 (µg/m³)", aq["pm10"])
    msg = f"Air quality is **{aq['category']}** (level {aq['level']} of 5)."
    (st.success if aq["level"] <= 1 else st.warning if aq["level"] <= 3 else st.error)(msg)

    profile = {"home": home, "cooking": cooking, "commute": commute, "sensitive": sensitive}
    saving = commute_saving(commute, alt, km) if km else None
    if saving and saving["co2_saved_kg"] > 0:
        st.info(f"Switching from {commute} to {alt} could save about "
                f"**{saving['co2_saved_kg']} kg CO₂/month** (rough estimate).")

    key = api_key()
    plan = None
    if key:
        try:
            with st.spinner("Personalising with Gemini..."):
                plan = gemini_plan(build_prompt(profile, aq, place["name"], saving), key)
        except Exception:
            st.warning("AI advice is unavailable right now, showing the standard plan.")
    if plan is None:
        plan = rule_based_plan(profile, aq)
    st.markdown(plan)
    st.caption("General guidance, not medical advice. Data: Open-Meteo air-quality API.")
