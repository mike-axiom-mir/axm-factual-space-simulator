# Installed package consumer path

The Python package can run outside the repository checkout without network access.
Build the wheel from a verified source tree, then install that local artifact.
For a transferable artifact whose exact bytes can be reproduced in the same declared
build toolchain, use the fail-closed builder:

```text
python tools/build_reproducible_wheel.py --output-dir dist
python -m pip install --no-index --no-deps dist/axm_factual_star_adventure_simulator-0.15.0-py3-none-any.whl
axm-star-sim generate --seed FIRST-EXPEDITION --output ./expedition
axm-star-sim verify-ledger --output ./expedition
```

The reproducible builder first requires the repository's canonical package seal to
verify. It then performs two clean wheel builds with a fixed ZIP-compatible
`SOURCE_DATE_EPOCH`, compares the complete wheel bytes, and publishes nothing unless
the builds are byte-identical. On PASS it prints an
`axm.reproducible-wheel-build-receipt.v1` JSON receipt containing the artifact SHA-256,
byte count, source-manifest/checksum identities, the Python/build-tool versions used,
and explicit false release/merge/CANON authority.

A normal command such as `python -m pip wheel .` remains valid for ordinary local
installation, but it is not the byte-reproducibility contract: ZIP member timestamps
or future build-tool behavior can make two ordinary wheel archives differ even when
the extracted files are equivalent. Keep the receipt and SHA-256 with a transferred
artifact when exact identity matters.

The build packages the canonical JSON registries directly from the repository's
`data/` directory. Runtime lookup prefers those source or installed resources over
a caller's current-directory `data/` folder, so an unrelated local file cannot
silently replace simulator truth. Resource paths are bounded to that data root.

The wheel is an offline execution boundary, not a release or authority boundary.
A matching SHA-256 proves content identity, not who built or approved the artifact.
The reproducibility check is scoped to repeated builds under the recorded Python,
setuptools and wheel toolchain; it does not promise byte identity across arbitrary
future backend versions or platforms unless those combinations are separately
measured.

Repository maintenance commands such as `axm-package-seal` and `axm-handoff` audit
a full source handoff and are not substitutes for validating a wheel. The automated
installed-package regression builds in an isolated temporary copy, compares every
packaged registry byte with its canonical source, installs without an index, runs
the real command shim from an unrelated working directory, and separately proves
that the reproducible builder emits identical wheel bytes after source-file mtimes
are changed without changing source content.
