# Action Report — Living Operations Bridge v0.7 Repair Attempt + Verification Gate

## Existing capability reused

The repository already had:
- a logistics/maintenance/spares/fabrication system;
- bounded repair-duration estimation and constrained fabrication interactions;
- v0.5 evidence-gated failure procedures and hash-chained procedure receipts;
- v0.6 derived system/room topology and repair-access routes.

v0.7 does not replace any of those systems.

## Added

`src/axm_star_sim/repair_verification.py` adds the missing lifecycle boundary:

1. build a repair gate from the existing procedure + topology;
2. require a completed, receipt-valid procedure session before staging;
3. require an externally sourced repair plan for the same target system;
4. refuse unsourced spare consumption;
5. refuse unvalidated fabricated repair parts;
6. record an external repair execution receipt without treating its claim as success;
7. require post-repair evidence and independent checks;
8. normalize unsupported “effective” claims to INCONCLUSIVE;
9. make only a verified effective result `fault_clearance_eligible=true`;
10. create a separate fault-clearance candidate that still has `fault_cleared=false` and `may_clear_fault=false`.

The low-pixel bridge receives a five-stage evidence ladder:
procedure receipt → repair plan → external execution → post-repair verification → authoritative clearance.

## Truth / authority boundary

This candidate records and verifies evidence. It does not:
- invent a component repair method;
- execute a repair;
- authorize physical access;
- consume a spare;
- validate a fabricated part by existence alone;
- modify runtime resources or time;
- clear a fault;
- claim a repair succeeded from an executor’s own result claim.

Status: DRAFT CANDIDATE / NOT CANON.
