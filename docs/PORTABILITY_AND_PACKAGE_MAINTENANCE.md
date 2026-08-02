# Portability and package maintenance

This package is designed to remain usable from a copied folder without a cloud account. Its deterministic simulation state is independent from the replaceable visual layer.

## Preserved source handoff

The original v0.15.0 handoff is an immutable intake artifact. Improvements are made in a separate working directory, not directly inside that source snapshot. Keep the original ZIP and its recorded SHA-256 when moving or rebuilding the branch.

## Portable launchers

The Windows and POSIX launchers resolve the package root from their own location. They explicitly request UTF-8 input/output and disable bytecode writes so behavior does not depend on a machine's legacy console code page or leave package noise behind.

Run the complete local acceptance gate:

```text
run_local_acceptance.bat
```

or on a POSIX shell:

```text
./run_local_acceptance.sh
```

## Deterministic package seal

`PACKAGE_MANIFEST.json` and `CHECKSUMS.sha256` describe the canonical package files. Generated demonstrations under `output/` have their own snapshot and are deliberately excluded from the canonical seal.

Check the existing seal without writing anything:

```text
run_package_seal_check.bat
```

Equivalent direct command:

```text
python tools/reseal_package.py --check
```

After an intentional, reviewed package change, rebuild the seal explicitly:

```text
python tools/reseal_package.py --write
```

The writer sorts paths, uses normalized JSON, excludes its own generated seal files and replaces both seal files atomically. Run the full local acceptance gate immediately afterward.

## Safe maintenance sequence

1. Preserve the received handoff and work in a separate lane.
2. Make bounded changes without rewriting simulation history.
3. Run unit tests and the full handoff audit.
4. Regenerate demonstrations only when their source changed.
5. Reseal the canonical package deliberately.
6. Re-run package verification after the final write.
7. Promote to the active storage location only after the destination is responsive and the copy can be verified.

Passing code tests proves deterministic and structural behavior. It does not prove live rendering; visual claims require a permitted browser or desktop observation route.
