# Save-Slot Ship Start Integration v1

New save slots should include a `ship_start_pin` generated from the bridge visual core.

Required pinned fields:

- bridge archetype ID/version;
- timeline start ID/version;
- crew start ID/version;
- initial render profile ID/version;
- semantic anchor list;
- start package receipt;
- pin receipt.

Older v0.9 slots remain valid without this field. A loader may attach a compatibility pin only when the user explicitly chooses a start-package mapping. It may not guess and silently rewrite an old slot.

Future ship selection belongs at adventure creation:

```text
choose universe/timeline start
→ choose vessel archetype
→ choose crew start
→ choose initial renderer
→ validate compatibility
→ pin exact versions in save slot
→ begin expedition
```
