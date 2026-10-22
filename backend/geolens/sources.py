"""Quota-aware public data adapters and an attributed OSM-extract fallback."""
import asyncio
import hashlib
import json
import math
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from shapely.geometry import shape, Point, LineString, Polygon
from shapely.ops import transform, unary_union
from pyproj import Transformer
from .config import settings
from .engine import distance_km, SPORTS


def candidate_matches(tags, activity):
    if tags.get("indoor") == "yes" or tags.get("access") == "no":
        return False
    if activity in SPORTS:
        return SPORTS[activity] in tags.get("sport", "").split(";") or (activity == "golf" and tags.get("leisure") == "golf_course")
    if activity == "cycling":
        return tags.get("highway") == "cycleway" or tags.get("route") == "bicycle" or tags.get("bicycle") == "designated"
    if activity == "hiking":
        return tags.get("highway") in {"path", "footway", "track"} or tags.get("route") == "hiking"
    if activity == "outdoor_photography":
        return tags.get("tourism") == "viewpoint" or tags.get("leisure") in {"park", "garden"}
    return tags.get("leisure") in {"park", "garden", "recreation_ground", "track"} or tags.get("tourism") == "picnic_site"


def selectors(activity):
    if activity in SPORTS:
        return [f'[sport~"(^|;){SPORTS[activity]}(;|$)"]'] + (["[leisure=golf_course]"] if activity == "golf" else [])
    return {"cycling": ['[highway=cycleway]', '[route=bicycle]'], "hiking": ['[highway~"^(path|footway)$"]'],
            "outdoor_photography": ['[tourism=viewpoint]', '[leisure=park]']} .get(activity, ['[leisure~"^(park|garden|recreation_ground|track)$"]', '[tourism=picnic_site]'])


def geometry(element):
    if element.get("geojson"):
        return shape(element["geojson"])
    coordinates = [(p["lon"], p["lat"]) for p in element.get("geometry", [])]
    if len(coordinates) > 3 and coordinates[0] == coordinates[-1]:
        return Polygon(coordinates)
    if len(coordinates) > 1:
        return LineString(coordinates)
    if "lon" in element:
        return Point(element["lon"], element["lat"])
    center = element.get("center")
    return Point(center["lon"], center["lat"]) if center else None


class Sources:
    def __init__(self):
        Path(settings.database).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(settings.database, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, saved REAL, data TEXT)")
        self.client = httpx.AsyncClient(headers={"User-Agent": settings.user_agent}, timeout=12, follow_redirects=False)
        self.locks = {}
        self.geocode_lock = asyncio.Lock()
        self.last_geocode = 0.
        self.overpass_lock = asyncio.Lock()

    async def fetch(self, url, params=None, ttl=900, timeout=12):
        key = hashlib.sha256(json.dumps([url,params], sort_keys=True).encode()).hexdigest()
        async with self.locks.setdefault(key, asyncio.Lock()):
            row = self.db.execute("SELECT saved,data FROM cache WHERE key=?", (key,)).fetchone()
            if row and time.time()-row[0] < ttl:
                return json.loads(row[1]), {"retrieved_at": datetime.fromtimestamp(row[0], timezone.utc).isoformat(), "cache": True, "url": url}
            response = await self.client.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            if len(response.content) > 5_000_000:
                raise ValueError("Source payload exceeded 5MB budget")
            data = response.json()
            saved = time.time()
            self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (key,saved,json.dumps(data)))
            self.db.commit()
            return data, {"retrieved_at": datetime.fromtimestamp(saved, timezone.utc).isoformat(), "cache": False, "url": url, "sha256": hashlib.sha256(response.content).hexdigest()}

    async def geocode(self, text):
        async with self.geocode_lock:
            await asyncio.sleep(max(0, 1.1-(time.monotonic()-self.last_geocode)))
            try:
                return await self.fetch("https://nominatim.openstreetmap.org/search", {"q": text, "format": "jsonv2", "countrycodes": "in", "limit": 3, "addressdetails": 1}, 604800)
            finally:
                self.last_geocode = time.monotonic()

    async def overpass(self, query):
        errors = []
        async with self.overpass_lock:
            for url in settings.overpass_urls.split(","):
                try:
                    payload, meta = await self.fetch(url.strip(), {"data": query}, 21600, timeout=13)
                    if payload.get("remark"):
                        raise ValueError("Incomplete Overpass response")
                    meta.update({"licence": "ODbL", "attribution": "© OpenStreetMap contributors", "osm_base": payload.get("osm3s", {}).get("timestamp_osm_base")})
                    return payload["elements"], meta
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    errors.append(type(exc).__name__)
            raise RuntimeError("Overpass unavailable: " + ",".join(errors))

    def extract(self, lat, lon, radius):
        path = Path(settings.osm_extract_database)
        if not path.exists():
            raise RuntimeError("No imported OSM extract available; run scripts/import_osm.py")
        dx, dy = radius / (111.32*math.cos(math.radians(lat))), radius/110.57
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as db:
            metadata = dict(db.execute("SELECT key,value FROM metadata"))
            bounds = json.loads(metadata["bounds"])
            if not (bounds[0] <= lon-dx and bounds[1] <= lat-dy and bounds[2] >= lon+dx and bounds[3] >= lat+dy):
                raise RuntimeError("Requested area exceeds imported extract coverage")
            rows = db.execute("SELECT data FROM features JOIN bounds_index USING(id) WHERE minx<=? AND maxx>=? AND miny<=? AND maxy>=? LIMIT 20001", (lon+dx,lon-dx,lat+dy,lat-dy)).fetchall()
            if len(rows) > 20000:
                raise RuntimeError("Extract query exceeds feature budget; reduce radius")
            return [json.loads(r[0]) for r in rows], {"url": metadata["source_url"], "retrieved_at": metadata["downloaded_at"], "osm_base": metadata.get("osm_timestamp"), "licence": "ODbL", "attribution": "© OpenStreetMap contributors / Geofabrik", "mode": "osm_extract", "extract_age_warning": "Snapshot geography; weather is freshly retrieved", "cache": False}

    async def venues(self, lat, lon, radius, activity):
        area = f"(around:{int(radius*1000)},{lat:.6f},{lon:.6f})"
        query = "[out:json][timeout:10];(" + "".join("nwr"+area+s+";" for s in selectors(activity)) + ");out tags center 80;"
        try:
            elements, meta = await self.overpass(query)
        except RuntimeError:
            elements, meta = await asyncio.to_thread(self.extract, lat, lon, radius)
        candidates, seen = [], set()
        for e in elements:
            tags = e.get("tags", {})
            if not candidate_matches(tags, activity):
                continue
            g = geometry(e)
            if g is None or g.is_empty:
                continue
            center = g.representative_point()
            distance = distance_km(lat,lon,center.y,center.x)
            key = (tags.get("name", ""), round(center.x,4), round(center.y,4))
            if distance > radius or key in seen:
                continue
            seen.add(key)
            candidates.append({"id": f"{e['type']}/{e['id']}", "name": tags.get("name") or tags.get("name:en") or f"Mapped {activity.replace('_',' ')} location", "lat": center.y, "lon": center.x,
                "distance_km": round(distance,3), "tags": tags, "features": {}, "geometry": e.get("geojson")})
        candidates.sort(key=lambda v: (v["tags"].get("access") in {"private","customers","members"}, v["distance_km"]))
        return candidates[:8], meta

    async def features(self, lat, lon, radius, venues):
        # Limit to the local search extent. Large-area searches explicitly omit proxies.
        if radius > 8:
            return {"status": "unavailable", "reason": "Feature coverage omitted for broad search; no invented proxies"}
        area = f"(around:{int((radius+1)*1000)},{lat:.6f},{lon:.6f})"
        query = "[out:json][timeout:8];("+"".join("way"+area+s+";" for s in ['[highway~"^(motorway|trunk|primary|secondary)$"]','[landuse=industrial]','[natural=water]','[natural=wood]','[landuse=forest]','[leisure=park]'])+");out geom 1500;"
        try:
            elements, meta = await self.overpass(query)
            if len(elements) >= 1500:
                return {"status": "unavailable", "reason": "Feature query truncated"}
        except RuntimeError:
            try:
                elements, meta = await asyncio.to_thread(self.extract,lat,lon,radius+1)
            except RuntimeError as exc:
                return {"status": "unavailable", "reason": str(exc)}
        zone = int((lon+180)/6)+1
        project = Transformer.from_crs(4326, 32600+zone if lat>=0 else 32700+zone, always_xy=True).transform
        groups = {k: [] for k in ("roads","industry","water","green")}
        geojson = []
        for e in elements:
            tags = e.get("tags", {})
            group = "roads" if tags.get("highway") in {"motorway","trunk","primary","secondary"} else "industry" if tags.get("landuse") == "industrial" else "water" if tags.get("natural") == "water" else "green" if tags.get("natural") == "wood" or tags.get("landuse") == "forest" else None
            if not group:
                continue
            g = geometry(e)
            if g is None or not g.is_valid:
                continue
            groups[group].append(transform(project,g))
            geojson.append({"type":"Feature","properties":{"kind":group},"geometry":g.__geo_interface__})
        unions = {k: unary_union(v) if v else None for k,v in groups.items()}
        for v in venues:
            p = transform(project,Point(v["lon"],v["lat"]))
            b = p.buffer(300)
            v["features"] = {"road_distance_m": round(p.distance(unions["roads"]),1) if unions["roads"] is not None else 99999,
                "industry_distance_m": round(p.distance(unions["industry"]),1) if unions["industry"] is not None else 99999,
                "water_distance_m": round(p.distance(unions["water"]),1) if unions["water"] is not None else None,
                "green_fraction": round(b.intersection(unions["green"]).area/b.area,3) if unions["green"] is not None else 0,
                "interpretation": "Mapped features only; absence of a mapped feature does not prove real-world absence"}
        return {**meta,"status":"available","geojson":{"type":"FeatureCollection","features":geojson}}

    async def forecasts(self, venues):
        latitudes = ",".join(str(v["lat"]) for v in venues)
        longitudes = ",".join(str(v["lon"]) for v in venues)
        common = {"latitude": latitudes,"longitude":longitudes,"timezone":"Asia/Kolkata","forecast_days":7}
        weather, aq = await asyncio.gather(
            self.fetch("https://api.open-meteo.com/v1/forecast", {**common,"hourly":"temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code,is_day,cloud_cover", "daily":"sunrise,sunset"},900),
            self.fetch("https://air-quality-api.open-meteo.com/v1/air-quality", {**common,"domains":"cams_global","hourly":"pm2_5,us_aqi"},1800), return_exceptions=True)
        if isinstance(weather, Exception):
            raise RuntimeError("Weather forecast unavailable") from weather
        wd, wm = weather
        wd = wd if isinstance(wd,list) else [wd]
        ad, am = ([], {"status":"unavailable"}) if isinstance(aq,Exception) else aq
        ad = ad if isinstance(ad,list) else [ad]
        for i,v in enumerate(venues):
            w = wd[i]
            a = ad[i] if i<len(ad) else {}
            aqs = {t: (a["hourly"]["us_aqi"][j],a["hourly"]["pm2_5"][j]) for j,t in enumerate(a.get("hourly",{}).get("time",[]))}
            v["weather_grid"] = {"lat": w["latitude"], "lon":w["longitude"]}
            v["aq_grid"] = {"lat":a.get("latitude"),"lon":a.get("longitude"),"resolution_km":45,"kind":"modeled_air_quality","native_time_step_hours":3}
            h = w["hourly"]
            mapping = {"temperature":"temperature_2m","apparent_temperature":"apparent_temperature","rain_probability":"precipitation_probability","rain_mm":"precipitation","wind_kmh":"wind_speed_10m","wind_direction":"wind_direction_10m","gust_kmh":"wind_gusts_10m","weather_code":"weather_code","is_day":"is_day","cloud_cover":"cloud_cover"}
            v["hours"] = [{"time":t+":00+05:30", **{key:h.get(field,[None]*len(h["time"]))[j] for key,field in mapping.items()}, "us_aqi":aqs.get(t,(None,None))[0],"pm2_5":aqs.get(t,(None,None))[1]} for j,t in enumerate(h["time"])]
            v["daylight"] = w.get("daily",{})
        return {"weather": {**wm,"kind":"forecast","licence":"CC BY 4.0","attribution":"Open-Meteo / weather model providers"}, "air_quality": {**am,"kind":"modeled_air_quality","resolution_km":45,"attribution":"Open-Meteo / Copernicus CAMS"}}
