# Rare UI source

AI Status adapted from https://github.com/swamimalode07/rare-ui/blob/8944172746e8e836aea2061790ee16b0577dd655/components/ui/ai-status.tsx

Copyright (c) 2026 Swami Malode. Licence: MIT + Commons Clause License Condition v1.0 + Attribution, retained in RareUI-LICENSE.txt.

Adaptation: local class-name join utility; GeoLens styles supplied through data-slot selectors in conversation.css; actual backend stage labels replace generic default labels. Motion and react-use-measure remain dependencies. Visible attribution appears in the website footer and README.

ThemeToggle is also adapted from components/ThemeToggle.tsx at the same commit. Its contrast SVG is retained; the Next-specific theme hook is replaced with controlled React props and a sliding thumb. GeoLens stores the explicit preference locally and initially follows the system theme.
