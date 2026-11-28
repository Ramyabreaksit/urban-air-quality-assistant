import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pytest
from advice import build_prompt, commute_saving, rule_based_plan, sanitize_city
from aqi import AirQualityError, aqi_category, fetch_air_quality, geocode


@pytest.mark.parametrize("aqi,label,level", [
    (0, "Good", 0), (50, "Good", 0), (51, "Moderate", 1), (120, "Unhealthy for sensitive groups", 2),
    (180, "Unhealthy", 3), (250, "Very unhealthy", 4), (450, "Hazardous", 5)])
def test_aqi_category(aqi, label, level):
    assert aqi_category(aqi) == (label, level)


def test_aqi_negative_rejected():
    with pytest.raises(ValueError):
        aqi_category(-1)


def test_sanitize_city():
    assert sanitize_city("  Chennai<script>  ") == "Chennaiscript"
    assert len(sanitize_city("a" * 500)) == 60
    assert sanitize_city(None) == ""


def test_commute_saving():
    s = commute_saving("Car", "Bus / metro / train", 10)
    assert s["monthly_km"] == 440.0 and s["co2_saved_kg"] > 0
    assert commute_saving("Walk / cycle", "Car", 10)["co2_saved_kg"] == 0
    with pytest.raises(ValueError):
        commute_saving("Rocket", "Car", 5)


def test_rule_plan_high_aqi_mentions_mask():
    aq = {"aqi": 220, "level": 4, "category": "Very unhealthy"}
    plan = rule_based_plan({"home": "Apartment", "commute": "Car", "cooking": "Wood / biomass", "sensitive": []}, aq)
    assert "N95" in plan and "Cooking smoke" in plan and "draught" in plan


def test_rule_plan_good_air():
    aq = {"aqi": 30, "level": 0, "category": "Good"}
    assert "acceptable" in rule_based_plan({"commute": "Walk / cycle"}, aq)


def test_prompt_contains_data():
    aq = {"aqi": 150, "level": 2, "category": "Unhealthy for sensitive groups", "pm2_5": 60, "pm10": 90}
    p = build_prompt({"home": "Apartment", "commute": "Car", "cooking": "LPG / gas", "sensitive": ["Young children"]}, aq, "Delhi", None)
    assert "Delhi" in p and "150" in p and "Young children" in p


class FakeResp:
    def __init__(self, data): self._d = data
    def raise_for_status(self): pass
    def json(self): return self._d


def test_geocode_and_air(monkeypatch):
    import aqi
    monkeypatch.setattr(aqi.requests, "get", lambda *a, **k: FakeResp(
        {"results": [{"name": "Chennai", "admin1": "Tamil Nadu", "country": "India", "latitude": 13.08, "longitude": 80.27}]}))
    assert geocode("chennai")["name"] == "Chennai, Tamil Nadu, India"
    monkeypatch.setattr(aqi.requests, "get", lambda *a, **k: FakeResp({"current": {"us_aqi": 160, "pm2_5": 70, "pm10": 100}}))
    assert fetch_air_quality(1, 1)["level"] == 3


def test_geocode_not_found(monkeypatch):
    import aqi
    monkeypatch.setattr(aqi.requests, "get", lambda *a, **k: FakeResp({}))
    with pytest.raises(AirQualityError):
        geocode("zzzz")


def test_sections_are_separate_and_complete():
    from advice import _indoor_section, _routine_section, _swaps_section
    assert _routine_section(0, False)[0] == "### Today's routine"
    assert any("Sensitive" in line for line in _routine_section(2, True))
    assert not any("Sensitive" in line for line in _routine_section(2, False))
    assert any("chimney" in line for line in _indoor_section("Apartment", "Wood / biomass"))
    assert any("carpool" in line for line in _swaps_section("Car"))
    assert any("already low-emission" in line for line in _swaps_section("Bus / metro / train"))


def test_commute_saving_clamps_distance():
    huge = commute_saving("Car", "Walk / cycle", 10_000)
    capped = commute_saving("Car", "Walk / cycle", 200)
    assert huge == capped


def test_fetch_air_quality_missing_aqi(monkeypatch):
    import aqi
    monkeypatch.setattr(aqi.requests, "get", lambda *a, **k: FakeResp({"current": {"us_aqi": None}}))
    with pytest.raises(AirQualityError):
        fetch_air_quality(1, 1)
