---
name: GeoLens field atlas
description: Conversational outdoor decision explorer
colors:
  ink: "#142D38"
  canvas: "#F2F0E7"
  paper: "#F7F6F0"
  primary: "#006C78"
  vegetation: "#426E59"
  line: "#D8DED8"
typography:
  body:
    fontFamily: "Source Sans 3, Noto Sans Devanagari, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.45
  display:
    fontFamily: "Source Sans 3, sans-serif"
    fontSize: "57px"
    fontWeight: 400
    lineHeight: 0.96
rounded:
  sm: "3px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "13px 15px"
---
# GeoLens website design

Approved direction: Monsoon field atlas. Mode: Operate, with conversation and cartography sharing the workspace.

## Overview
Monsoon field atlas: a calm coastal cartographic surface whose task is to compare real places and hours. The map, matrix and evidence remain synchronized.

## Colors
Coastal ink for decisions, mineral surfaces for controls, a restrained green suitability scale. Restriction states also use words and patterns.

## Typography
Locally bundled Source Sans 3 and Noto Sans Devanagari; serif emphasis in the opening heading. Tabular numerals carry times and measurements.

## Layout
Desktop: persistent left conversation with fixed composer; real geographic map and synchronized hourly decision surface on the right. Mobile: Chat by default, with separate Map, Compare and Details tabs. Main recommendation stays distinct from manual map selection. Rare UI inline status follows actual backend tool events, honors reduced motion, and never reveals or simulates chain-of-thought.

## Elevation & Depth
One offset soft shadow distinguishes the query/evidence sheets from the map. No glass, neon glow or decorative gradients.

## Shapes
Fine straight rules, small-radius controls and circular numbered venue markers. Patterned unknown states differ from scored cells.

## Components
Selection synchronizes the venue marker, hour, weather summary, ranking and exact score contribution changes. No source-value animation or invented map field. Reduced motion disables camera flight.

## Do's and Don'ts
Initial map has no analysis. Only an actually captured snapshot may be offered as a labeled saved result. Loading follows real work. Outages, missing venue/access/terrain/AQ, no-suitable-option and model unavailability remain visible. OSM/OpenFreeMap attribution is persistent.

Dark mode uses forest charcoal surfaces, sage ink accents and matching map controls. It preserves suitability and avoidance distinctions. A compact Rare UI theme slider persists the choice; historical satellite imagery keeps original colors.
