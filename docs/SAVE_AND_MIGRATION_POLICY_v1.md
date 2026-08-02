# Save and Migration Policy v1

Existing expeditions are historical records, not mutable templates.

Allowed compatibility work includes visual reconstruction, additive registry adapters, derived-index rebuilds, non-lossy format wrappers and explicit forks. The original pin remains present and verifiable.

A migration is rejected when it changes pinned bridge, timeline, crew, interior, ship, commitment, semantic anchors, roots, seeds or historical ledgers. It is held when rollback or branch identity is missing.

Use:

```bash
python -m axm_star_sim.migration_cli create --start-pin pin.json --migration-type visual_reconstruction --changes-json '{"target_render_profile_id":"axm.render.future.v2"}' --output proposal.json
python -m axm_star_sim.migration_cli assess --proposal proposal.json
```
