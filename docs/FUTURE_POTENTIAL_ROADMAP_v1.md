# Future Potential Roadmap v1

These are research and build ideas, not implemented capabilities.

## FUTURE-001 — Compartment fluid and atmosphere network
**Priority:** high

Replace the lumped cabin model with room-level gas, pressure, ventilation and isolation nodes.

**Potential:** Leaks, smoke and contamination become spatial rather than global.

**Boundary:** Keep human-health interpretation bounded and validate conservation.

**Depends on:** ship interior, ECLSS, fault management

## FUTURE-002 — Full navigation covariance and geometry
**Priority:** high

Add covariance matrices, relative-motion geometry and optional SPICE adapters.

**Potential:** Encounters and rendezvous gain realistic uncertainty ellipsoids and closing geometry.

**Boundary:** Do not imply precision unsupported by ephemeris or sensor data.

**Depends on:** GNC, sensor registry, atlas

## FUTURE-003 — Procedure and checklist engine
**Priority:** high

Bind alerts and failure modes to versioned, role-authorized procedures with hold points.

**Potential:** Crew can train, execute and review realistic procedures.

**Boundary:** Procedures must not invent a successful repair or bypass command authority.

**Depends on:** station displays, fault registry, qualification

## FUTURE-004 — Damage topology and repair graph
**Priority:** high

Represent components, lines, buses, zones, access paths, spares and repair dependencies.

**Potential:** Damage produces local consequences and meaningful repair expeditions.

**Boundary:** Avoid fake component specificity until source-pinned or clearly assumed.

**Depends on:** ship interface graph, maintenance, rooms

## FUTURE-005 — Effects-first tactical encounter geometry
**Priority:** high

Model detection, relative geometry, maneuver, occlusion, power, heat, communications and damage propagation.

**Potential:** Supports tense conflict, rescue and avoidance without arbitrary hit points.

**Boundary:** No real-world weapon-construction instructions; intent remains evidence-bounded.

**Depends on:** GNC, sensors, ship systems, encounters

## FUTURE-006 — Multi-ship and docking registry
**Priority:** medium

Add independent ship archetypes, compatible interfaces, transfer manifests and shared events.

**Potential:** Allows fleets, visitors, rescue craft and radically different starting ships.

**Boundary:** Each ship keeps independent authority, resources and history.

**Depends on:** migration policy, start registries, docking

## FUTURE-007 — Crew procedure learning and cross-training
**Priority:** medium

Turn competency evidence into scheduled simulations, supervised tasks and cross-role qualification.

**Potential:** Crew evolution becomes visible through actual work rather than XP.

**Boundary:** Learning pressure never automatically promotes skill.

**Depends on:** competency ledger, procedures, rooms

## FUTURE-008 — Long-duration soak and corruption laboratory
**Priority:** high

Run millions of deterministic turns, randomized save/reload, partial-write and corruption tests.

**Potential:** Proves whether the world survives long campaigns and interrupted local operation.

**Boundary:** Store reproducible failure seeds and do not hide flaky cases.

**Depends on:** all ledgers, migration, handoff doctor

## FUTURE-009 — Instrument plugin library
**Priority:** medium

Register real and hypothetical-bounded instruments with calibration, noise and observation channels.

**Potential:** Planets and anomalies can be studied through distinct factual tools.

**Boundary:** Instrument capability must be source-pinned or assumption-labelled.

**Depends on:** science station, source registry, evidence ladder

## FUTURE-010 — Holodeck and renderer adapter contract
**Priority:** medium

Allow 2D, 2.5D, 3D and cinematic renderers to consume immutable room, ship and event semantics.

**Potential:** Graphics can improve dramatically without rewriting expedition history.

**Boundary:** Renderer never becomes world authority.

**Depends on:** bridge lock, room graph, migration policy

## FUTURE-011 — Coexisting Village shared inhabitant kernel
**Priority:** high

Port rooted option eligibility, role authority, provenance, learning evidence and append-only relationships into the village.

**Potential:** Tests the same principled autonomy in a social and economic world.

**Boundary:** Avoid reducing inhabitants to utility optimizers or hidden morality scores.

**Depends on:** four roots, competency, resource ownership

## FUTURE-012 — Local authoritative multiplayer host
**Priority:** medium

Synchronize human and machine participants through deterministic intent packets and signed state updates.

**Potential:** Friends can join expeditions without giving clients world authority.

**Boundary:** Offline single-player remains complete; networking is optional.

**Depends on:** save slots, command modes, network adapter

## FUTURE-013 — Scientific source refresh pipeline
**Priority:** medium

Import reviewed official catalog snapshots while preserving previous revisions and source dates.

**Potential:** Factual baselines can improve without silently changing old saves.

**Boundary:** No live source may overwrite pinned historical facts.

**Depends on:** source registry, atlas, technology cores

## FUTURE-014 — Private medical and wellbeing boundary
**Priority:** medium

Separate private crew reports, task-fitness decisions and public operational consequences.

**Potential:** Crew wellbeing can matter without exposing private narratives to every subsystem.

**Boundary:** No fake mind score and no medical diagnosis without a validated model.

**Depends on:** medical station, agency root, privacy policy

## FUTURE-015 — Autonomous crew sandbox and counterfactual rehearsal
**Priority:** high

Let crew test proposed actions in cloned state branches before requesting execution.

**Potential:** Clever autonomy gains foresight without experimenting on canonical reality.

**Boundary:** Counterfactual outcomes remain simulations and may not be presented as observed facts.

**Depends on:** rooted reasoning, ship state, command gates
