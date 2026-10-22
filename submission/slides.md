# GeoLens — six-slide presentation source

## 1. Find the right place and the right hour
People need a decision, not isolated forecasts. GeoLens compares real nearby venues over full outdoor activity windows. Its signature is a synchronized geographic map and venue × hour matrix.

## 2. A worked example, with evidence
Insert an ACTUAL captured response and desktop screenshot after live end-to-end verification. Show two venues, two forecast hours, a changed constraint, score contributions and source timestamps. Do not invent an example result to fill this slide.

## 3. Architecture and scientific boundary
Question → local SLM intent → geocoding → OSM/Geofabrik venues → live weather/CAMS AQ → geographic measurements → deterministic restrictions/scoring → SLM comparative predicates → validation → JSON and map.

Geography fallback stores attributed OSM features, not answers. Forecasts remain retrieved per query/cache TTL. Road proximity is not traffic; CAMS Global AQ is regional, not a park sensor.

## 4. One small, self-hosted model
Qwen3.5-2B, full released count 2,274,069,824; Apache-2.0. Text-only Q4_K_M via llama.cpp, thinking disabled and bounded JSON generation. No fine-tuning. Interpretation and evidence comparison are genuine model calls; Python checks facts and numerical comparisons.

Insert measured Hindi/English quality, model RAM/latency and public HF load verification only when measured. Original-format release preparation is included; public identity is pending.

## 5. Verification and reliability
Ten activity profiles; critical tests cover storm duration, access, sensitivity, missing evidence, time interpretation and unsupported model claims. Insert actual test totals, warm/cold latency, concurrency, memory and browser captures from the readiness report. Do not present targets as achieved measurements.

## 6. Honest limits and public deliverables
Incomplete venue/access data, coarse regional atmospheric forecasts, no live traffic, no booking/medical guarantees. One model, no paid/private inference/data. Code, API and HF links remain PENDING until actually published/deployed.

AI coding tools: OpenAI Codex. No sub-agents used.
