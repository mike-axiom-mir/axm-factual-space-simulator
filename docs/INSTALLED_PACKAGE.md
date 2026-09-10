# Installed package consumer path

The Python package can run outside the repository checkout without network access.
Build the wheel from a verified source tree, then install that local artifact:

```text
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
python -m pip install --no-index --no-deps dist/axm_factual_star_adventure_simulator-0.15.0-py3-none-any.whl
axm-star-sim generate --seed FIRST-EXPEDITION --output ./expedition
axm-star-sim verify-ledger --output ./expedition
```

The build packages the canonical JSON registries directly from the repository's
`data/` directory. Runtime lookup prefers those source or installed resources over
a caller's current-directory `data/` folder, so an unrelated local file cannot
silently replace simulator truth. Resource paths are bounded to that data root.

The wheel is an offline execution boundary, not a release or authority boundary.
Its metadata and files describe the source revision from which it was built; they
do not authenticate the builder or make generated adventures factual observations.
Keep the wheel together with its source revision and an independently recorded
SHA-256 digest when transferring it.

Repository maintenance commands such as `axm-package-seal` and `axm-handoff` audit
a full source handoff and are not substitutes for validating a wheel. The automated
installed-package regression builds in an isolated temporary copy, compares every
packaged registry byte with its canonical source, installs without an index, and
runs the real command shim from an unrelated working directory.
