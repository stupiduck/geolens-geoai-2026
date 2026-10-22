from datetime import datetime
from zoneinfo import ZoneInfo

from geolens.engine import evaluate, compare, upwind_alignment, resolve_time, ACTIVITIES


def venue():
    return {"id": "way/1", "name": "Fixture court", "lat": 19.1, "lon": 72.9,
            "tags": {"sport": "tennis", "leisure": "pitch"}, "distance_km": 1,
            "features": {"road_distance_m": 100, "green_fraction": None}}


def hours():
    return [{"time": "2026-10-23T08:00:00+05:30", "temperature": 28,
             "apparent_temperature": 29, "rain_probability": 0, "rain_mm": 0,
             "wind_kmh": 4, "wind_direction": 180, "weather_code": 0,
             "is_day": 1, "us_aqi": 40},
            {"time": "2026-10-23T09:00:00+05:30", "temperature": 29,
             "apparent_temperature": 30, "rain_probability": 90, "rain_mm": 6,
             "wind_kmh": 6, "wind_direction": 180, "weather_code": 95,
             "is_day": 1, "us_aqi": 40}]


def test_wind_from_south_places_southern_source_upwind():
    assert upwind_alignment(180, 180) == 1
    assert upwind_alignment(0, 180) == 0


def test_all_ten_profiles_exist():
    assert len(ACTIVITIES) == 10


def test_long_window_cannot_hide_later_thunderstorm():
    result = evaluate([venue()], hours(), "tennis", {"duration_minutes": 120})
    assert result[0]["eligibility"] == "avoid"
    assert "thunderstorm" in result[0]["warning_codes"]


def test_missing_coverage_and_unknown_factors_do_not_improve_score():
    result = evaluate([venue()], hours()[:1], "tennis", {"duration_minutes": 120})
    assert result[0]["eligibility"] == "insufficient_data"
    assert result[0]["score_low"] <= result[0]["score_high"]


def test_private_venue_cannot_win_public_request():
    v = venue()
    v["tags"]["access"] = "private"
    assert evaluate([v], hours(), "tennis", {})[0]["eligibility"] == "excluded"


def test_sensitive_profile_tightens_pollution_advice():
    h = hours()[:1]
    h[0]["us_aqi"] = 180
    general = evaluate([venue()], h, "tennis", {})[0]
    sensitive = evaluate([venue()], h, "tennis", {"pollution_sensitive": True})[0]
    assert general["eligibility"] != "avoid"
    assert sensitive["eligibility"] == "avoid"


def test_counterfactual_delta_matches_contributions():
    r = evaluate([venue()], hours(), "tennis", {})
    delta = compare(r[0], r[1])
    assert abs(sum(x["delta"] for x in delta["contributions"]) - delta["score_delta"]) < 0.01


def test_ist_weekend_is_anchored_once():
    start, end = resolve_time("this weekend", datetime(2026, 10, 22, 20, tzinfo=ZoneInfo("Asia/Kolkata")))
    assert start.date().isoformat() == "2026-10-24"
    assert end.date().isoformat() == "2026-10-26"
