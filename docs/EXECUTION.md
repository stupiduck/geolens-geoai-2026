# GeoLens execution ledger

The revised local-first instructions supersede the initial plan. No production access, SSH, changes or public exposure are authorized at this stage. No sub-agents were used.

- Implemented independent JSON API, asynchronous UI jobs, one local Qwen3.5-2B, actual geography/weather/AQ, ten activity profiles and verified comparative predicates.
- Public Overpass failed locally. Added attributed, coverage-checked Geofabrik SQLite/RTree fallback. It stores geography rather than answers; forecasts and computations remain query-specific.
- Rejected the smaller 0.8B pilot after Hindi/constraint failures. Selected one 2B model, 2K context, two threads, thinking off.
- Corrected location choices to preserve original text/script with separate coordinates/ID. Added compound-location and commute-priority safeguards, plus cross-profile AQ policy tests.
- Impeccable used for the website only; single-context visual QA follows the user's prohibition on delegation. Reports remain Markdown.
- Compose parses; Linux deployment/resource enforcement remains unverified.
- Pinned original-format model weights/tokenizer/config/licence are staged locally. Public identities/upload and external API are still acceptance gates.
- Existing user plan, rulebook PDF, AGENTS.md and New Text Document.txt are preserved.

See READINESS.md for measurements, limitations and the approval-gated deployment proposal.
