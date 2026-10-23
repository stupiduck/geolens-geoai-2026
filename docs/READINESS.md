# GeoLens local readiness

22 October 2026. Local only. No production server has been accessed or modified.

Website: http://localhost:5173. Independent JSON API/OpenAPI: http://127.0.0.1:8000/docs. Readiness: /readyz.

## Verified implementation

FastAPI; real Qwen3.5-2B inference; English/Hindi interpretation; ten activity profiles; actual OSM venues, hourly weather and regional modeled AQ; geographic scoring; synchronized map/time comparison; source ledger; sensitivity counterfactual; attributed 2024 satellite toggle. Location choices retain the original question/script with coordinates and OSM ID in a separate field. Commutes request origin/destination before other clarification.

71 critical tests pass, covering all activities, complete windows, storms, private access, missing data, unsupported claims, compound locations, preserved Hindi, commute priority and consistent AQ policy across activities/profiles. Fixtures supplement genuine live HTTP/browser checks.

## Measurements

Ryzen AI 9 HX 370, 24 logical processors, 24.8 GB RAM; Windows; llama.cpp b11819; Q4_K_M; two generation threads; 2K context; one slot; thinking off.

| Check | Actual result |
| --- | --- |
| Two concurrent requests | Both HTTP 200, 8.172–9.195 s |
| Five concurrent requests | All HTTP 200, 17.335–20.987 s; no 429 |
| Model peak working set in these runs | 1,531–1,905 MiB |
| API peak working set in these runs | 133–138 MiB |
| Model sampled CPU | Peak ~206% in psutil notation, about two logical cores |
| Warm Lonavala hiking | HTTP 200, 8 candidates, 5.586 s |
| Hindi Powai release query | HTTP 200, 8 candidates, 11.779 s |

Small samples do not establish p95 or uptime. A cold Lonavala request during large download/import work took 63.349 s. Windows RSS varies with paging and is not Linux cgroup memory. A sequential 0.8B pilot failed Hindi/constraint checks and was rejected. The selected runtime remains one 2B model.

Raw evidence: load-test-2.json, load-test-5.json, live-smoke.json, release-check.json. Final release verification is appended below.

## Data and limits

Attributed Geofabrik/OSM extracts store geography, never answers. The Western Zone rectangle covers Mumbai/Pune/Lonavala. The Southern Zone import adds Bangalore coverage. Bounds/completion metadata are checked. Other resolvable Indian areas use bounded Overpass; an outage beyond imported coverage returns unavailable. Weather cache TTL is 15 minutes, AQ 30 minutes. No India-wide offline coverage is claimed.

CAMS Global US AQI is regional (~45 km), not CPCB AQI or a park sensor. Road/industry/green factors are mapped proxies. Terrain describes a sampled mapped segment when elevation works; Lonavala's live elevation retrieval was unavailable and disclosed. Complete routes, travel-time routing, exact opening hours, booking and medical clearance are not implemented. Satellite imagery is historical context, excluded from environmental scoring.

## Remaining release gates

Pinned original-format model weights, tokenizer/config and Apache licence are staged under models/hf-staging. Public GitHub/HF identities, upload and clean public from_pretrained verification are pending. Local staged files do not satisfy the public model gate. An external HTTP endpoint and judging-window uptime remain pending. No public links are fabricated.

Compose parses; a full Linux container build/run is not yet verified. Limits: API 640 MiB / 0.5 CPU; model 2,700 MiB / 1.5 CPU; web 96 MiB / 0.1 CPU. Total caps ~3.36 GiB plus host/Docker/existing services. A shared 4 GB host may not fit. These are provisional limits, not production sizing measurements. Data binds only the dedicated GeoLens directory; Linux must permit UID 10001 to write its cache.

After explicit approval, the next deployment step is a read-only inventory of free RAM, CPU/disk, existing container usage and occupied ports. Then propose a separate directory and isolated Compose project with measured headroom and a reversible shutdown procedure. No existing service restarts, pruning, volume removal, firewall or shared reverse-proxy changes are authorized.

AI coding disclosure: OpenAI Codex. Impeccable applied to the website. No sub-agents or paid/private runtime inference/data APIs.

Original-format local `from_pretrained` load and generation succeeded using Transformers 5.20.2 and CPU Torch 2.14.1, local files only. 2,213,241,664 parameters were loaded by the inference class. The complete released tensor count also includes upstream auxiliary tensors. This load-only smoke took 115.648 s under memory pressure, uses reference CPU kernels and is not runtime API latency or a grounding-quality test. Public upload/load remains pending. The quantized server was restored afterward. See hf-load-verification.json and scripts/requirements-release.lock.txt.

Bengaluru final real query passed: HTTP 200, eight venues, 14.397 s, Southern Zone extract plus retrieved weather/AQ. Its earlier failures exposed the dense-city venue-budget bug; the regression test verifies activity filtering occurs before that budget. The Southern database contains 367,880 imported features. `docs/interactions.json` verifies the real async-job, compare and sensitivity endpoints with exact contribution deltas and consistent avoidance.

## Packaged local artifacts

- Six-slide presentation: ../submission/GeoLens.pptx (editable source: ../submission/build_slides.cjs).
- 72-second video: ../submission/GeoLens-demo.mp4. It is an edited walkthrough of genuine captured screens, not continuous real-time footage. Captions/storyboard are included.
- Actual desktop, satellite, comparison, Bengaluru, Hindi and mobile captures: ../output/playwright/.
- Final frontend build, dependency audit (zero findings), Compose parsing and 71-test suite passed. No Linux container build/run or external uptime claim is made.

Local environment files are excluded from Git and Docker build context. Credentials inadvertently shown in a tool result require rotation by their owner; no secret values are included in release artifacts.


## Conversational correction verified, 23 October 2026

71 automated tests pass after the conversation and AQ policy corrections. Production frontend build passes. Real local Qwen plus actual OSM/forecast queries verified: Powai running 4.787 s; relative two-hour follow-up 8.210 s; greener follow-up 10.403 s; Hindi language follow-up 10.598 s. All returned HTTP 200 with an appropriate no-suitable-option outcome under the conservative air policy. Place, activity, concrete time window and greener preference were retained. These are individual observations, not p95. Raw records: conversation-live.json.

Final compound-location checks: Lonavala hiking HTTP 200, 6.025 s; underspecified office cycling HTTP 200 with route clarification, 3.224 s; Hindi Powai/asthma HTTP 200 with Powai preserved and avoidance, 4.575 s. Raw records: conversation-correctness-live.json. An earlier Hindi parser boundary bug and follow-up model flag repetition were found with real inference and fixed, with regression tests.

Frontend now uses actual Rare UI AI Status source, with its distinct Commons Clause and attribution licence retained. Activity is inferred; optional Preferences allow explicit overrides. Conversation state is bounded process memory, cleared on API restart. Browser stores only an opaque identifier. Screenshots and edited-video materials are refreshed separately; no external/public availability is implied. Existing infrastructure remains untouched.

Dark mode added using a controlled Rare UI ThemeToggle adaptation, with a persisted local preference and initial system-theme selection. Street cartography is styled dark; satellite imagery remains unfiltered. Evidence is a repeat-click toggle, with overlay pointer handling so the same desktop button remains accessible. Per request, no additional automated test pass was run for these reversible UI additions. The 71-test result above covers the functional conversation implementation before the theme addition.

Submission presentation and 72-second edited capture walkthrough rebuilt on 23 October. Public publication, Linux-container execution and external endpoint verification remain incomplete gates.
