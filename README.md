# GeoLens

Plan outdoor activities across real places and upcoming hours using Qwen3.5-2B, mapped geography and hourly forecasts.

Website: https://geo.setuconsultants.in · API: https://geo.setuconsultants.in/docs

Model: https://huggingface.co/manavmodi/geolens-geoai-2026

The public core is deployed. Latest optional web-search and contrast changes are available locally and in source; production rollout is held while localhost is reviewed. See `docs/PERFORMANCE.md` for measured timings and costs.

## Run locally (Windows)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe scripts/prepare_local_model.py --model 2b
.\models\runtime\llama-server.exe -m models/Qwen3.5-2B-Q4_K_M.gguf --host 127.0.0.1 --port 8081 -t 2 -tb 2 -c 2048 -np 1 -b 128 -ub 32 --jinja --reasoning off --no-webui
```

In separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn geolens.app:app --app-dir backend --host 127.0.0.1 --port 8000
npm.cmd ci --prefix frontend
npm.cmd run dev --prefix frontend
```

Website: http://localhost:5173. JSON API/docs: http://127.0.0.1:8000/docs. Health/readiness: `/healthz` and `/readyz`. `.env.example` lists configurable model, cache and URL settings. Nothing needs a browser session or hosted model API key.

On Linux, use Unix virtualenv paths and the Linux llama-server binary. The downloader verifies file length and SHA-256 and records model provenance in `models/local-manifest.json`.

## OSM-extract fallback

Completed OSM extracts are preferred within their coverage. Elsewhere, bounded Overpass queries use a five-minute circuit breaker after outages. Geographic extracts and forecast caches refresh independently; suitability is computed for each query.

```powershell
.\.venv\Scripts\python.exe scripts/download_osm.py --region western-zone
.\.venv\Scripts\python.exe scripts/import_osm.py data/extracts/western-zone.osm.pbf --source-url https://download.geofabrik.de/asia/india/western-zone-latest.osm.pbf --bounds 72.7,18.4,74.1,19.6
```

The Western Zone rectangle covers Mumbai–Pune–Lonavala. A second Southern Zone database covers Bengaluru (77.3,12.7,77.9,13.3), configured via GEOLENS_OSM_EXTRACT_EXTRA_DATABASES; additional database paths can be separated by semicolons. It is **not India-wide fallback coverage**. Other resolvable Indian areas use the same live pipeline; when Overpass fails and their geography is not imported, return unavailable rather than inventing venues. Import another appropriate Geofabrik extract with a conservatively covered rectangle for broader fallback coverage. Only point/way/area features are stored, with source, date, licence and query bounds. An import may take several minutes and uses a disk-backed node cache; do not query its in-progress database.

Attribution: **© OpenStreetMap contributors**, ODbL; regional download by Geofabrik. https://www.openstreetmap.org/copyright and https://download.geofabrik.de/asia/india.html. Do not redistribute extracted databases as application code under the code licence; retain the applicable database licence and source metadata.

For Bengaluru fallback, download the Southern Zone and import it separately:

```powershell
.\.venv\Scripts\python.exe scripts/download_osm.py --region southern-zone
.\.venv\Scripts\python.exe scripts/import_osm.py data/extracts/southern-zone.osm.pbf --source-url https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf --bounds 77.3,12.7,77.9,13.3 --output data/osm-southern.sqlite
```

## API

```powershell
$body = @{question='Where should I run tomorrow morning near Powai, Mumbai?';include=@('evidence','hourly','geojson')} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/v1/recommend -Method Post -ContentType application/json -Body $body
```

`POST /ask` is the synchronous compatibility route. `POST /v1/analyses` supports polling and SSE progress. `/compare` returns contribution differences; `/scenario` recomputes sensitivity from the same evidence snapshot.

Responses include intent, venues, recommendations, restrictions, evidence, model identity and timings. Domain outcomes include clarification, no suitable option and insufficient data. Unavailable inference returns HTTP 503, deadlines 504 and invalid input 422.

Supported activities: running, cycling, golf, cricket, football, tennis, hiking/nature walk, picnic, outdoor gathering, photography. Commute-specific route planning currently returns explicit clarification/unavailability; it does not invent a route. Exact opening-hours parsing, booking, full-trip route verification and country-polygon validation remain limitations.

## Model and scientific boundaries

Qwen3.5-2B original revision `15852e8c16360a2fea060d615a32b45270f8a8fc`, full released count 2,274,069,824 including vision/MTP; Apache-2.0. Text-only Q4_K_M via llama.cpp; one loaded model. No fine-tuning. A compact schema interprets English/Hindi constraints; a second real SLM call compares options using typed predicates verified by Python. Explicit sensitivity mentions are preserved even when the small model omits them.

Weather: Open-Meteo model forecasts, not observations. AQ: CAMS Global regional modeled US AQI (~45 km; native 3-hourly), not Indian CPCB AQI or a park sensor. Road/industry/green features are mapped proxies, not live traffic, concentrations or tree-canopy measurements. Terrain, if available, describes a sampled real mapped segment, not a fabricated complete hiking/cycling route. Scores/ranges are heuristic suitability/missing-data bounds, not calibrated confidence or medical clearance.

No claim is made that an outdoor activity is safe merely because a forecast/score is favorable. Unknown access, lighting, weather fields and terrain remain explicit. Whole activity windows are checked; future storms cannot hide behind a favorable start hour.

## Sources and usage

- Nominatim: submit-only geocoding, <=1 request/s, identifying User-Agent, cache and OSM attribution. https://operations.osmfoundation.org/policies/nominatim/
- Overpass/Private.coffee: bounded public queries and respectful concurrency; ODbL. https://dev.overpass-api.de/overpass-doc/en/preface/commons.html and https://overpass.private.coffee/
- Open-Meteo weather/AQ: non-commercial public hackathon prototype only, CC BY 4.0 data, credit Open-Meteo and Copernicus CAMS/providers. https://open-meteo.com/en/terms and https://open-meteo.com/en/docs/air-quality-api
- OpenTopoData SRTM30m: historical elevation; credit NASA/USGS; 100 points/request, 1 request/s, 1,000 requests/day. https://www.opentopodata.org/
- Satellite: EOX Sentinel-2 cloudless 2024 mosaic, modified Copernicus Sentinel data, CC BY-NC-SA 4.0. Historical context only; not live imagery or an input to scores. https://maps.eox.at/
- OpenFreeMap/OpenMapTiles/OSM: public vector basemap; persistent attribution. https://openfreemap.org/quick_start/
- AQ advice: EPA/AirNow US-AQI guidance; not a conversion to Indian AQI. https://document.airnow.gov/air-quality-guide-for-particle-pollution.pdf

Run without subscriptions, ads, commercial promotion or lead capture under the selected free weather service terms. Do not silently monetize this service without re-evaluating source terms. Local development uses llama.cpp on the local machine. The authorized production configuration uses the existing authenticated Modal endpoint, with spending controls. Optional Tavily search uses the supplied backend key; neither service has been upgraded to a paid plan.

## Verification and mandatory artifacts

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/probe_sources.py
.\.venv\Scripts\python.exe scripts/benchmark_model.py
npm.cmd run build --prefix frontend
npm.cmd audit --prefix frontend
```

HF release files/card/upload and clean-load scripts are under `hf-release/` and `scripts/publish_model.py`, `scripts/verify_hf_load.py`. The public checkpoint is published under `manavmodi/geolens-geoai-2026`; public-ID loading and generation passed using SHA-verified identical cached weights. See `docs/hf-public-load-verification.json`. No credentials are printed. Six-slide and demo-video sources are under `submission/`; final captures/results must be genuine.

Docker Compose configuration is under `deploy/`. All ports bind loopback by default and the model stays private. The isolated production API is capped at 512 MiB / 0.4 CPU and Nginx at 48 MiB / 0.1 CPU. The observed API working set after live queries was 198 MiB; Nginx used 4.2 MiB. See `docs/DEPLOYMENT.md`. No prune, volume deletion, firewall change or shared-proxy modification is part of this setup.

**AI coding disclosure:** OpenAI Codex assisted research, coding, tests and design implementation. No sub-agents were used. Impeccable was used for the product website; visual review was performed in the same session per user instruction. Proprietary coding AI is not called by the running application.

## Conversational interface and API

Activity and constraints are inferred from the message; Preferences are optional overrides. Desktop keeps chat, map and comparison visible. Mobile provides Chat, Map, Compare and Details views. Map selection inspects a candidate without rewriting the assistant recommendation.

Each `/v1/analyses` or `/v1/recommend` reply returns an opaque `conversation_id`. Send that ID with the next original `question` to retain structured place, time, activity and constraints. Relative time shifts anchor to the prior recommendation. Location disambiguation submits `location: {id, name, latitude, longitude}` separately and preserves the original question and script. `GET /v1/conversations/{id}` restores recent turns and the current analysis. Memory is process-local, bounded to 32 conversations and 20 turns, and expires after an idle hour; restarting the API clears it. Use a single API worker. Only the opaque ID is stored in browser localStorage. Treat it as private; production transport must use HTTPS.

Actual pipeline events include status and measured stage duration. The frontend uses a source-adapted [Rare UI](https://rareui.com) AI Status component, copyright 2026 Swami Malode, pinned to commit `8944172746e8e836aea2061790ee16b0577dd655`. Its MIT + Commons Clause + Attribution terms are retained in `frontend/src/vendor/RareUI-LICENSE.txt`; this exception is not covered by the application code licence. No simulated web searches or hidden reasoning traces are displayed.

An existing OpenAI-compatible Qwen endpoint can be configured through `GEOLENS_MODEL_URL`. Optional `GEOLENS_MODEL_API_KEY` or Modal proxy key/secret settings are server-only. Never expose credentials in Vite variables. The local verified default remains the single resident llama.cpp model. No new hosted deployment is created by this configuration.

Rule version 2026-10-23.2 uses conservative regional US-AQI planning cutoffs: intense activities avoid at 151, or 101 for sensitive profiles; other activities avoid at 201, or 151 for sensitive profiles. These are planner policies informed by [AirNow guidance](https://document.airnow.gov/air-quality-guide-for-particle-pollution.pdf), not personal medical clearance. Rain probability affects suitability and explicit caution, while intense rain, thunder and wind restrictions remain separate.

The header theme switch adapts Rare UI’s ThemeToggle, follows the system theme initially and remembers an explicit local choice. Evidence opens and closes from the same button. Satellite pixels retain their natural colors in either theme.

## Optional web notices

Enable **Web** beside Send to check recent official-domain notices. Set `TAVILY_API_KEY` on the backend only. Searches use basic depth, four results, no generated answer, a seven-second timeout and no retries. A persistent one-hour cache and conservative reservations limit this app to 10 requests/day and 100/month by default. Limits are configurable; zero disables requests. This is an app-level limit, not an account-wide billing guarantee.

Search runs for the first opted-in plan, changed area/activity/day or explicit notice questions. Same-plan follow-ups reuse notices. Notices preserve URLs, retrieval time and publication dates when supplied; missing dates remain unknown. Search excerpts are unverified and never determine venue eligibility, weather or AQ values. No closure notice does not establish that a venue is open. Failures leave the core analysis intact.
