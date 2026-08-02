# AXM branch backfeed

This lane carries only branch capabilities that can stand on their own. It does
not copy space-simulator identity, story, saves, datasets, rendering, or runtime
state into the Workshop.

`backfeed.recipe.json` names reviewed source modules. `tools/build_platform_backfeed.py`
copies them into `dist/`, rejects external dependencies and path escapes, and
writes a SHA-256 inventory in `dist/AXM_BRANCH_CAPSULE.json`.

The first capsule contains:

- `deterministic-json-core`: strict cross-runtime canonical JSON;
- `immutable-history-guard`: proposal assessment that refuses silent pinned-history changes;
- `branch-backfeed-lab`: a browser-side capsule verifier that emits a review receipt and never installs or promotes code.

Build and verify:

```text
python tools/build_platform_backfeed.py --write
python tools/build_platform_backfeed.py --check
```

Prepare a bounded Workshop install:

```text
python tools/install_platform_backfeed.py --workshop D:\AXM_ACTIVE\workshop --plan
python tools/install_platform_backfeed.py --workshop D:\AXM_ACTIVE\workshop --apply --plan-digest <digest>
```

Apply refuses existing targets. It adds leaf folders under `tools/`; it does not
edit the registry, hub entrypoint, foundation spine, permissions, or CANON state.
Graft/review remains the promotion gate.
