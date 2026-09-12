# Action Report — Living Operations Bridge v0.6 Damage Topology Steward Run

## Decision

The repository already contained most of the conceptual pieces requested by roadmap FUTURE-004:

- `ship_interface_graph.json` already defines system-to-system interfaces;
- `ship_system_blueprint_registry.json` already binds systems to rooms and declares dependencies;
- `ship_interior_archetype_registry.json` already defines room adjacency and travel times;
- `room_interaction_registry.json` already contains bounded repair-duration estimation and constrained fabrication;
- the v0.5 branch already binds ship failure modes to evidence-gated procedures.

Therefore v0.6 does **not** introduce a second ship graph or invented component inventory.

## Added

### `src/axm_star_sim/damage_topology.py`

A deterministic resolver that composes those existing registries into one read-only damage/repair-access view.

For each failure it derives:

- the authoritative source system;
- direct inbound/outbound interfaces;
- source-declared system dependencies;
- mapped interior rooms;
- unresolved external/service room bindings;
- a shortest known room path using the existing room graph and travel-time table;
- a link to the v0.5 failure procedure when available;
- whether the abstract maintenance system, repair-duration estimator, and constrained fabrication interaction exist.

### Critical truth boundary

The new graph is **system-level only**.

It deliberately does not invent:

- valves;
- cable runs;
- individual bus branches;
- fasteners;
- access panels;
- spare-part SKUs;
- replacement part compatibility;
- repair durations for a specific fault.

Those remain `UNKNOWN_COMPONENT_SPECIFICITY_NOT_PINNED` until a later source-pinned component topology exists.

### Low-pixel bridge extension

`damage_topology_v0_6.js/css` adds:

- a compact topology graph for the selected failure drill;
- direct-interface neighbor nodes;
- repair-access route visualization through known rooms;
- unresolved/external-binding visibility;
- maintenance capability / spares-boundary status;
- runtime receipts that keep repair, spares consumption, fabrication, fault clearing and neighbor-failure claims forbidden.

The display follows the selected v0.5 failure procedure automatically.

## Focused verification before GitHub publication

- damage topology focused suite: **9 PASS + 1 repository-integration test staged for CI**;
- Python syntax: PASS for topology and integration sources;
- JavaScript syntax: PASS under `node --check`.

The repository-integration test loads the actual canonical data files inside CI and verifies that all declared failure modes resolve into the existing graph without enabling repair authority.

## Authority boundary

v0.6 may:

- derive and display graph proximity;
- show known room routes;
- show unresolved bindings;
- show whether abstract maintenance capabilities exist;
- link a failure to its review procedure.

v0.6 may **not**:

- propagate a failure to neighbor systems merely because an interface exists;
- execute an automatic response;
- enter a compartment;
- consume a spare;
- fabricate or validate a repair part;
- execute a repair;
- clear a fault;
- mark repair verified;
- alter runtime state or truth labels.

Status: **DRAFT CANDIDATE / NOT CANON**.
