# Ship Interior Room System v1

## Canonical direction

The first vessel is a lived-in, explorable ship rather than a single command room.

Its initial interior contains:

- Command Deck
- Central Corridor
- Mess Hall
- Engineering
- Research and Strategy Room
- Primary Explorer Quarters
- AI Collaborator Quarters

This is one versioned interior archetype. Future ships may use different rooms, shapes, cultures, command structures, or embodiments.

## Room graph

Rooms are spatial nodes with bidirectional connections and travel time. A room cannot become an unrelated web page. Movement is recorded in an append-only visit chain.

## Functional rule

Every room has a role in the simulation.

- Mess Hall: consumable calculations, debriefs, crew-reported wellbeing.
- Engineering: power, heat, repairs, calibration, radiation-risk indices, fabrication.
- Research: evidence comparison, false-positive controls, mission planning.
- Quarters: logs, rest records, provenance-tracked artifacts, customization.
- Command Deck: irreversible decisions, encounters, navigation, command recall.

## Extensibility

Breaking room changes require a new interior version or ID. Existing saves retain their pinned room graph and interaction versions.
