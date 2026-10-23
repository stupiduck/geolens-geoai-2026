# GeoLens
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
Approved: React/TypeScript/Vite, MapLibre, FastAPI, local llama.cpp, SQLite. Existing server preferred.

## Users
Hackathon judges and people planning outdoor activities in India. They need an understandable place/time comparison and its evidence.

## Product Purpose
Recommend real nearby places and upcoming activity windows using retrieved geography, forecasts and personal constraints.

## Positioning
Interactive place × time decision surface with computed counterfactual changes and inspectable evidence.

## Capabilities and Constraints
Ten activities, English/Hindi text, arbitrary resolvable Indian locations. One self-hosted model below 3B parameters. No paid/private inference or data. No invented measurements, live traffic or confidence probabilities. API works independently of website. Structured multi-turn context preserves original messages, location choices, constraints and language. Desktop combines conversation and persistent cartography; mobile provides Chat, Map, Compare and Details.

## Evidence on Hand
Local rulebook and approved implementation plan. Genuine local API responses and browser captures exist under docs/ and output/playwright/. Public release and deployment gates remain pending.

## Accessibility & Inclusion
Keyboard-operable time matrix, result list independent of map, reduced motion, mobile layouts, readable Hindi and explicit missing-data states.

## Product Principles
Evidence before persuasion. Unknown stays unknown. Full activity windows, not favorable single hours. Show exactly what changed. Preserve existing server services.
