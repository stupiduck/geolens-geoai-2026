---
language:
- en
- hi
license: apache-2.0
base_model: Qwen/Qwen3.5-2B
library_name: transformers
pipeline_tag: image-text-to-text
tags:
- geolens
- geospatial
- outdoor-planning
---

# GeoLens Qwen3.5-2B

Unchanged Qwen3.5-2B base checkpoint used by GeoLens. This repository includes the original weights, configuration, tokenizer and Apache-2.0 licence.

Base model: `Qwen/Qwen3.5-2B`, revision `15852e8c16360a2fea060d615a32b45270f8a8fc`. Full release count, including vision and MTP tensors: 2,274,069,824. Quantization does not change architectural eligibility. No fine-tuning has been performed.

Production uses the existing Modal Dedicated Endpoint with the unchanged base checkpoint. Local development also used a text-only Q4_K_M conversion. This repository contains the original Transformers files for reproducible `from_pretrained` loading. Retain the upstream Apache-2.0 licence and notices; application code is separately licensed.

## Intended use

English/Hindi outdoor intent interpretation and constrained comparative reasoning over real retrieved geospatial/weather evidence. The model must not invent places, measurements, access permissions, live traffic, medical safety or statistically calibrated confidence. A deterministic engine performs geometry, numerical scoring, exclusions and predicate verification.

## Limitations

Model language competence, temporal interpretation and structured-output behavior require task validation. Regional air-quality forecasts cannot establish park-level exposure. OSM coverage/access details can be incomplete. Scores are planning heuristics. This is an educational non-commercial hackathon prototype, not a clinical or emergency service.

## Loading

Use `manavmodi/geolens-geoai-2026` with `AutoModelForImageTextToText.from_pretrained`, `AutoProcessor.from_pretrained` and `trust_remote_code=False`. Pin the repository commit for reproducibility. See https://github.com/stupiduck/geolens-geoai-2026 for the verification script.

## Development disclosure

OpenAI Codex assisted implementation. No hosted proprietary language model is called by the running application. The sole runtime language model is self-hosted. Public data sources and their separate terms are documented in the code repository.

## Local reproducibility check

Pinned original checkpoint contains 2,274,069,824 tensor elements (verified from the safetensors header). Transformers 5.20.2 with CPU Torch 2.14.1 successfully loaded and generated locally using `AutoModelForImageTextToText.from_pretrained`, `trust_remote_code=False` and local files only. Its inference class loaded 2,213,241,664 parameters; auxiliary upstream tensors account for the difference. This does not establish successful public Hub loading, which must be checked after publication. Use the separate release environment in `scripts/requirements-release.lock.txt`; local development used the quantized llama.cpp runtime.
