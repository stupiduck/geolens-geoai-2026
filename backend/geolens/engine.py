"""Pure, versioned suitability policies. Scores are heuristics, not probabilities."""
import math
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from astral import Observer
from astral.sun import elevation

IST = ZoneInfo("Asia/Kolkata")
RULE_VERSION = "2026-10-23.3"
# Conservative outing policies, not calibrated safety probabilities. Applied to
# every forecast hour, independently of the relative suitability score.
INTENSE_ACTIVITIES={'running','cycling','cricket','football','tennis','hiking'}
# thermal, AQ, rain/wind, activity fit, travel, geographic context, green
ACTIVITIES = {
    "running": [20, 25, 15, 20, 10, 5, 5],
    "cycling": [15, 25, 20, 20, 10, 10, 0],
    "golf": [15, 10, 30, 30, 10, 5, 0],
    "cricket": [20, 15, 25, 25, 10, 5, 0],
    "football": [20, 20, 20, 25, 10, 5, 0],
    "tennis": [15, 15, 30, 25, 10, 5, 0],
    "hiking": [15, 15, 20, 30, 10, 5, 5],
    "picnic": [25, 15, 20, 20, 10, 5, 5],
    "outdoor_gathering": [20, 15, 30, 20, 10, 5, 0],
    "outdoor_photography": [15, 10, 25, 35, 10, 5, 0],
}
FACTORS = ["thermal", "air_quality", "rain_wind", "venue_fit", "travel", "road_industry", "vegetation"]
DURATIONS = {"golf": 180, "hiking": 120, "picnic": 120, "outdoor_gathering": 120}
SPORTS = {"tennis": "tennis", "golf": "golf", "cricket": "cricket", "football": "soccer"}
RAIN_LIMITS = {a: (60 if a in {'picnic','outdoor_gathering','tennis'} else 70 if a in {'golf','cricket','football'} else 80,
                   2 if a in {'picnic','outdoor_gathering','tennis','golf'} else 5) for a in ACTIVITIES}


def clip(value):
    return max(0., min(1., value))


def upwind_alignment(source_bearing, wind_from):
    return max(0., math.cos(math.radians(source_bearing - wind_from)))


def distance_km(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b - a, math.radians(lon2 - lon1)
    x = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(x), math.sqrt(max(0, 1 - x)))


def resolve_time(expression, now=None):
    now = (now or datetime.now(IST)).astimezone(IST)
    text = expression.lower()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if any(x in text for x in ("weekend", "सप्ताहांत")):
        start = midnight + timedelta(days=(5 - now.weekday()) % 7)
        if now.weekday() == 6:
            start = midnight
        return max(start, now), start + timedelta(days=2 if now.weekday() != 6 else 1)
    day = midnight
    if "tomorrow" in text or "कल" in text or re.search(r'\bkal\b',text):
        day += timedelta(days=1)
    for name, index in [("monday",0),("tuesday",1),("wednesday",2),("thursday",3),("friday",4),("saturday",5),("sunday",6)]:
        if name in text:
            day = midnight + timedelta(days=(index - now.weekday()) % 7)
    if any(x in text for x in ("morning", "सुबह", "subah")):
        start, end = day.replace(hour=5), day.replace(hour=11)
    elif any(x in text for x in ("evening", "after work", "शाम", "shaam", "sham")):
        start, end = day.replace(hour=17), day.replace(hour=21)
    elif "afternoon" in text or "दोपहर" in text:
        start, end = day.replace(hour=12), day.replace(hour=17)
    elif "sunset" in text or "सूर्यास्त" in text:
        start, end = day.replace(hour=16), day.replace(hour=20)
    elif "tomorrow" in text or "कल" in text or day > midnight:
        start, end = day, day + timedelta(days=1)
    else:
        start, end = now, now + timedelta(hours=24)
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", text)
    if match:
        hour = int(match[1]) % 12 + (12 if match[3] == "pm" else 0)
        start = day.replace(hour=hour, minute=int(match[2] or 0))
        end = start + timedelta(hours=2)
    return max(start, now), end


def activity_fit(venue, activity):
    tags = venue["tags"]
    sports = tags.get("sport", "").split(";")
    if activity in SPORTS:
        return 0. if SPORTS[activity] in sports or (activity == "golf" and tags.get("leisure") == "golf_course") else None
    if activity == "cycling":
        return 0. if tags.get("highway") == "cycleway" or tags.get("route") == "bicycle" else .4
    return .2


def evaluate(venues, hours, activity, constraints):
    if activity not in ACTIVITIES:
        raise ValueError("Unsupported activity")
    duration = constraints.get("duration_minutes") or DURATIONS.get(activity, 60)
    sensitive = any(constraints.get(k) for k in ("pollution_sensitive", "child_present", "older_adult", "pregnancy"))
    weights = list(ACTIVITIES[activity])
    if sensitive:
        weights[1] *= 1.5
        weights[5] *= 1.5
    if constraints.get('prefer_greener'):
        weights[6]=max(weights[6],5)*2
    weights = [w * 100 / sum(weights) for w in weights]
    results = []
    for venue in venues:
        own_hours = venue.get("hours", hours)
        by_time = {datetime.fromisoformat(h["time"]): h for h in own_hours}
        for start in sorted(by_time):
            if constraints.get("start") and start < datetime.fromisoformat(constraints["start"]):
                continue
            if constraints.get("end") and start >= datetime.fromisoformat(constraints["end"]):
                continue
            end = start + timedelta(minutes=duration)
            needed = [start + timedelta(hours=i) for i in range(math.ceil(duration / 60))]
            window = [by_time[t] for t in needed if t in by_time]
            complete = len(window) == len(needed)
            warnings, limits = [], []
            eligibility = "eligible"
            tags, features = venue["tags"], venue.get("features", {})
            fit = activity_fit(venue, activity)
            if activity in {'picnic','outdoor_gathering'}:
                named = bool(tags.get('name') or tags.get('name:en') or (venue.get('name') and not venue['name'].startswith('Unnamed ')))
                appropriate = tags.get('leisure') in {'park','garden','recreation_ground'} or tags.get('tourism') == 'picnic_site'
                if not named or not appropriate or not venue.get('metadata',{}).get('destination_evidence_sufficient',True):
                    eligibility = 'insufficient_data'
                    limits.append('unverified_picnic_destination')
            if activity=='outdoor_photography':
                solar=elevation(Observer(venue['lat'],venue['lon']),start)
                fit=clip(abs(solar+1)/12) if constraints.get('photography_goal')=='sunset' else clip((abs(solar-10)-5)/30)
            if tags.get("access") in {"private", "no", "customers", "members"} or fit is None:
                eligibility = "excluded"
                warnings.append("restricted_or_incompatible_venue")
            if not complete or any(h.get("weather_code") is None for h in window):
                eligibility = "insufficient_data" if eligibility == "eligible" else eligibility
                limits.append("incomplete_activity_window")
            if constraints.get("max_travel_minutes") and venue.get("static_minutes") is None:
                eligibility = "insufficient_data" if eligibility == "eligible" else eligibility
                limits.append("travel_time_unverified")
            if constraints.get("avoid_steep_terrain") and features.get("max_grade_percent") is None:
                eligibility = "insufficient_data" if eligibility == "eligible" else eligibility
                limits.append("terrain_unverified")
            if features.get("max_grade_percent") is not None and constraints.get("max_grade_percent") is not None and features["max_grade_percent"] > constraints["max_grade_percent"]:
                eligibility = "excluded"
                warnings.append("grade_constraint_exceeded")
            if any(h.get("weather_code") in (95, 96, 99) for h in window):
                eligibility = "avoid" if eligibility != "excluded" else eligibility
                warnings.append("thunderstorm")
            probability_limit, amount_limit = RAIN_LIMITS[activity]
            weather_restrictions = [
                ('high_rain_probability', any(h.get('rain_probability') is not None and h['rain_probability'] >= probability_limit for h in window)),
                ('heavy_rain_for_activity', any(h.get('rain_mm') is not None and h['rain_mm'] >= amount_limit for h in window)),
                ('strong_wind_for_activity', any(h.get('wind_kmh') is not None and h['wind_kmh'] >= (30 if activity in {'cycling','golf','picnic','outdoor_gathering'} else 40) for h in window)),
            ]
            for code, applies in weather_restrictions:
                if applies:
                    eligibility = 'avoid' if eligibility != 'excluded' else eligibility
                    warnings.append(code)
            if any(any(h.get(k) is None for k in ('apparent_temperature','rain_probability','rain_mm','wind_kmh')) for h in window):
                eligibility = 'insufficient_data' if eligibility == 'eligible' else eligibility
                limits.append('essential_weather_unavailable')
            if constraints.get('child_present') and features.get('water_distance_m') is not None and features['water_distance_m']<100:
                warnings.append('near_water_supervise_children')
            aq = [h["us_aqi"] for h in window if h.get("us_aqi") is not None]
            if len(aq) != len(window):
                limits.append("regional_air_quality_unavailable")
                if sensitive and eligibility == "eligible":
                    eligibility = "insufficient_data"
            # Conservative planning cutoffs, not a medical definition of safety.
            cutoff=101 if sensitive and activity in INTENSE_ACTIVITIES else 151 if sensitive or activity in INTENSE_ACTIVITIES else 201
            if aq and max(aq) >= cutoff:
                if eligibility != "excluded":
                    eligibility = "avoid"
                warnings.append("pollution_avoid_intense_activity")
            elif aq and max(aq) > 100:
                warnings.append("pollution_reduce_intensity")
            if any(not h.get("is_day", 1) for h in window) and (activity in {"golf", "hiking"} or constraints.get("daylight_only")):
                eligibility = "excluded"
                warnings.append("insufficient_daylight")
            if constraints.get("end") and end>datetime.fromisoformat(constraints["end"]):
                eligibility="excluded"
                warnings.append("outside_requested_window")
            values = {k: [] for k in FACTORS[:3]}
            for h in window:
                temp = h.get("apparent_temperature")
                values["thermal"].append(None if temp is None else max(clip((temp - 26) / 12), clip((12 - temp) / 7)))
                values["air_quality"].append(None if h.get("us_aqi") is None else clip(h["us_aqi"] / 200))
                rain, prob, wind = h.get("rain_mm"), h.get("rain_probability"), h.get("wind_kmh")
                threshold = (10, 30) if activity in {"tennis", "outdoor_photography"} else (15, 40)
                values["rain_wind"].append(None if None in (rain, prob, wind) else .6 * max(clip(prob / 80), clip(rain / 3)) + .4 * clip((wind-threshold[0])/(threshold[1]-threshold[0])))
            penalties = {k: (max(v) if v and all(x is not None for x in v) else None) for k, v in values.items()}
            penalties["venue_fit"] = fit
            penalties["travel"] = clip(venue.get("distance_km", 0) / constraints.get("radius_km", 5))
            road, industry = features.get("road_distance_m"), features.get("industry_distance_m")
            penalties["road_industry"] = None if road is None or industry is None else clip(.6 * math.exp(-road/150) + .4 * math.exp(-industry/1000))
            if penalties["road_industry"] is not None:
                directional=[]
                for h in window:
                    wind=h.get("wind_kmh")
                    direction=h.get("wind_direction")
                    ralign=upwind_alignment(features["road_bearing_deg"],direction) if features.get("road_bearing_deg") is not None and direction is not None and wind is not None and wind>=3.6 else None
                    ialign=upwind_alignment(features["industry_bearing_deg"],direction) if features.get("industry_bearing_deg") is not None and direction is not None and wind is not None and wind>=3.6 else None
                    directional.append(.6*math.exp(-road/150)*(.5+.5*ralign if ralign is not None else 1)+.4*math.exp(-industry/1000)*(ialign if ialign is not None else 1))
                penalties["road_industry"]=clip(max(directional)) if directional else None
            penalties["vegetation"] = None if features.get("green_fraction") is None else 1-clip(features["green_fraction"])
            contributions = [{"factor": k, "weight": round(w, 4), "penalty": penalties[k], "points": None if penalties[k] is None else round(-w*penalties[k], 4)} for k,w in zip(FACTORS, weights)]
            known = sum(c["points"] or 0 for c in contributions)
            missing = sum(c["weight"] for c in contributions if c["points"] is None)
            low, high = round(100+known-missing, 2), round(100+known, 2)
            limits.extend(k+"_unknown" for k,p in penalties.items() if p is None and weights[FACTORS.index(k)] > 0)
            if "opening_hours" not in tags:
                limits.append("opening_hours_unverified")
            if "access" not in tags:
                limits.append("public_access_unverified")
            results.append({"id": f"{venue['id']}@{start.isoformat()}", "venue_id": venue["id"], "time": start.isoformat(), "end": end.isoformat(), "duration_minutes": duration,
                "score": round((low+high)/2, 2), "score_low": low, "score_high": high, "eligibility": eligibility,
                "warning_codes": warnings, "limitations": sorted(set(limits)), "contributions": contributions,
                "conditions": by_time[start], "coverage_complete": complete, "rule_version": RULE_VERSION})
    return results


def compare(before, after):
    diffs = [{"factor": a["factor"], "delta": round((b["points"] if b["points"] is not None else -b["weight"]/2) - (a["points"] if a["points"] is not None else -a["weight"]/2), 4)} for a,b in zip(before["contributions"], after["contributions"])]
    return {"before_id": before["id"], "after_id": after["id"], "score_delta": round(sum(x["delta"] for x in diffs), 4),
            "before_eligibility": before["eligibility"], "after_eligibility": after["eligibility"], "contributions": diffs}
