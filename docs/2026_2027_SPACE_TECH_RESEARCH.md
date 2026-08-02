# 2026–2027 Human Space Technology Research Snapshot

**Pinned on:** 2026-08-02  
**Planning horizon:** calendar year 2027  
**Purpose:** provide factual technology lineages for AXM ship generation without ranking, promotional interpretation, or invented specifications.

## 1. Orion + European Service Module

Role in AXM: flight-proven crew-transport lineage.

Pinned values in the local registry:

- crew capacity: 4 persons;
- standalone mission duration: up to 21 days;
- solar electrical generation: 11 kW;
- 33 engines across the published propulsion architecture;
- approximately 62 ft solar-array span;
- suited emergency life support: up to 144 hours;
- transparent derived maximum: 84 person-days, calculated as 4 × 21.

Sources: `nasa_orion_reference_2026`, `nasa_orion_components_2026`, `nasa_artemis_iii_2027`.

Blocked in AXM because this pinned snapshot does not contain enough reviewed values: wet-mass-specific acceleration, main-engine performance, delta-v capability, continuous artificial gravity, and interstellar operation.

## 2. Gateway PPE + HALO

Role in AXM: planned high-power solar-electric deep-space platform lineage.

Pinned values:

- 60 kW power and propulsion architecture;
- 3 AEPS units rated at 12 kW each;
- 4 BHT-6000 units rated at 6 kW each;
- transparent installed-thruster nameplate arithmetic: 60 kW;
- early crew capacity: 4;
- early crew stays: 30–90 days;
- uncrewed remote operation: up to 3 years;
- near-rectilinear halo orbit period: approximately 6.5 days;
- published lunar-distance range: approximately 1,500 km to 70,000 km.

Sources: `nasa_gateway_reference_2026`, `nasa_gateway_capabilities_2026`, `nasa_gateway_power_on_2026`, `nasa_aeps_qualification_2025`.

The 60 kW thruster-nameplate total is arithmetic, not a claim that every unit operates simultaneously or that 60 kW is available to payloads after platform loads.

## 3. SpaceX Starship HLS 2027 pathfinder lineage

Role in AXM: planned cryogenic lander/pathfinder lineage for the 2027 integrated Orion–HLS demonstration.

Pinned values:

- approximate published height: 50 m;
- a NASA TechPort cryogenic-transfer project objective of more than 3 metric tons of liquid oxygen.

Sources: `nasa_artemis_iii_2027`, `nasa_hls_2026`, `nasa_spacex_cfm_techport_2026`.

AXM does not infer that the transfer objective has flown successfully. It also leaves the exact 2027 test article’s mass, thrust, specific impulse, propellant load, payload, crew duration, and acceleration unknown.

## 4. Blue Moon Mark 2 HLS 2027 pathfinder lineage

Role in AXM: planned cryogenic lander/pathfinder lineage for the 2027 integrated demonstration.

Sources: `nasa_artemis_iii_2027`, `nasa_hls_2026`.

The pinned sources establish the program lineage and planned function, but not enough exact Mark 2 test-article performance values for AXM to calculate thrust, acceleration, delta-v, propellant endurance, payload, or crew duration. Those fields remain blocked.

Blue Moon Mark 1 and cryogenic-fluid-management work are retained only as supporting technology records. Their values are not silently transferred into Mark 2.

## 5. Cryogenic storage and transfer

Supporting records:

- `nasa_cfm_2026` — cryogenic fluid management program;
- `nasa_loxsat_2026` — planned in-orbit liquid-oxygen storage/transfer demonstration;
- `nasa_spacex_cfm_techport_2026` — large-scale Starship transfer project record;
- `nasa_blue_moon_mk1_2026` — Mark 1 demonstration lineage for cryogenic propulsion, precision landing, and autonomous guidance/navigation/control.

These technologies can open future simulation threads such as boil-off, tank conditioning, transfer losses, docking geometry, telemetry delay, and fault recovery only when the relevant equations and source values are added.

## 6. Nuclear thermal propulsion correction

Broader NASA nuclear-thermal research remains a research envelope under `nasa_ntp_2026`.

DRACO is **not** treated as an upcoming 2027 flight. The local status gates `nasa_draco_closeout_2026` and `darpa_draco_complete` record the April 2025 stop-work/complete status. Therefore it cannot occupy a near-term seed-selection slot.

## 7. 2027 mission interpretation

The pinned 2027 Artemis III plan is used as an integrated low-Earth-orbit rendezvous, docking, crew-transfer, and operations pathfinder. AXM does not rewrite it as the earlier lunar-surface mission architecture.

## Research limitations

This snapshot is not a complete survey of every national, commercial, military, or academic spacecraft project. The eligible catalog is intentionally small, traceable, and replaceable. A future reviewed source update may:

- add an eligible lineage;
- remove or suspend one whose schedule changes;
- add a newly published parameter;
- invalidate an earlier planning assumption;
- create a new registry version without silently changing old campaigns.
