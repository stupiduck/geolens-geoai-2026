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

Release preparation only: this directory is not a published or independently loadable Hub repository until the original weights/tokenizer/config files are staged and uploaded using `scripts/publish_model.py`.

Base model: `Qwen/Qwen3.5-2B`, revision `15852e8c16360a2fea060d615a32b45270f8a8fc`. Full release count, including vision and MTP tensors: 2,274,069,824. Quantization does not change architectural eligibility. No fine-tuning has been performed.

The runtime uses a text-only Q4_K_M conversion, with no vision projector loaded. The public artifact should also contain the exact original Transformers weights/configuration/tokenizer for reproducible `from_pretrained` loading. Retain the upstream Apache-2.0 licence and notices; application code is separately licensed.

## Intended use

English/Hindi outdoor intent interpretation and constrained comparative reasoning over real retrieved geospatial/weather evidence. The model must not invent places, measurements, access permissions, live traffic, medical safety or statistically calibrated confidence. A deterministic engine performs geometry, numerical scoring, exclusions and predicate verification.

## Limitations

Model language competence, temporal interpretation and structured-output behavior require task validation. Regional air-quality forecasts cannot establish park-level exposure. OSM coverage/access details can be incomplete. Scores are planning heuristics. This is an educational non-commercial hackathon prototype, not a clinical or emergency service.

## Loading

After publication, use the actual published repository ID and pinned release revision with the tested Transformers class for Qwen3.5, an AutoProcessor and text-only generation. `scripts/verify_hf_load.py` is the acceptance check; no successful public load is claimed before it runs.

## Development disclosure

OpenAI Codex assisted implementation. No hosted proprietary language model is called by the running application. The sole runtime language model is self-hosted. Public data sources and their separate terms are documented in the code repository.
