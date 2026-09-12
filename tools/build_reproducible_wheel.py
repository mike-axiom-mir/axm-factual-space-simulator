from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


RECEIPT_SCHEMA = "axm.reproducible-wheel-build-receipt.v1"
SOURCE_DATE_EPOCH = 315532800  # 1980-01-01T00:00:00Z, the ZIP format floor.


class WheelBuildError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _build_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "SOURCE_DATE_EPOCH": str(SOURCE_DATE_EPOCH),
            "TZ": "UTC",
        }
    )
    return environment


def _verify_source_seal(
    source_root: Path,
    environment: dict[str, str],
) -> tuple[dict[str, Any], bytes, bytes]:
    manifest_path = source_root / "PACKAGE_MANIFEST.json"
    checksums_path = source_root / "CHECKSUMS.sha256"
    sealer = source_root / "tools" / "reseal_package.py"
    for required in (manifest_path, checksums_path, sealer, source_root / "pyproject.toml"):
        if not required.is_file():
            raise WheelBuildError(
                "SOURCE_SEAL_INVALID",
                f"required verified-source file is missing: {required.name}",
            )

    manifest_before = manifest_path.read_bytes()
    checksums_before = checksums_path.read_bytes()
    completed = subprocess.run(
        [sys.executable, str(sealer), "--check"],
        cwd=source_root,
        env=environment,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise WheelBuildError(
            "SOURCE_SEAL_INVALID",
            "canonical source seal did not verify; refusing to build a transferable wheel",
        )
    manifest_after = manifest_path.read_bytes()
    checksums_after = checksums_path.read_bytes()
    if manifest_before != manifest_after or checksums_before != checksums_after:
        raise WheelBuildError(
            "SOURCE_SEAL_MOVED",
            "canonical seal files changed while they were being verified",
        )
    try:
        manifest = json.loads(manifest_after.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WheelBuildError("SOURCE_SEAL_INVALID", "package manifest is not valid UTF-8 JSON") from exc
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise WheelBuildError("SOURCE_SEAL_INVALID", "package manifest has no managed file map")
    return manifest, manifest_after, checksums_after


def _copy_verified_source(
    source_root: Path,
    destination_root: Path,
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    checksums_bytes: bytes,
) -> None:
    destination_root.mkdir(parents=True)
    files = manifest["files"]
    for relative in sorted(files, key=str.casefold):
        info = files[relative]
        if not isinstance(relative, str) or not relative or relative.startswith(("/", "\\")):
            raise WheelBuildError("SOURCE_SEAL_INVALID", "package manifest contains an unsafe path")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise WheelBuildError("SOURCE_SEAL_INVALID", "package manifest contains a path escape")
        if not isinstance(info, dict):
            raise WheelBuildError("SOURCE_SEAL_INVALID", "package manifest contains invalid file metadata")
        expected_bytes = info.get("bytes")
        expected_sha256 = info.get("sha256")
        if not isinstance(expected_bytes, int) or expected_bytes < 0:
            raise WheelBuildError("SOURCE_SEAL_INVALID", "package manifest contains an invalid byte count")
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            raise WheelBuildError("SOURCE_SEAL_INVALID", "package manifest contains an invalid SHA-256")

        source_path = source_root / relative_path
        if source_path.is_symlink() or not source_path.is_file():
            raise WheelBuildError(
                "SOURCE_BYTES_MOVED",
                f"managed source file changed type or disappeared: {relative}",
            )
        payload = source_path.read_bytes()
        if len(payload) != expected_bytes or _sha256_bytes(payload) != expected_sha256:
            raise WheelBuildError(
                "SOURCE_BYTES_MOVED",
                f"managed source bytes changed after seal verification: {relative}",
            )
        destination = destination_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    (destination_root / "PACKAGE_MANIFEST.json").write_bytes(manifest_bytes)
    (destination_root / "CHECKSUMS.sha256").write_bytes(checksums_bytes)


def _build_once(
    source_root: Path,
    environment: dict[str, str],
    manifest: dict[str, Any],
    manifest_bytes: bytes,
    checksums_bytes: bytes,
) -> tuple[str, bytes]:
    with tempfile.TemporaryDirectory(prefix="axm-wheel-build-") as temporary:
        temporary_root = Path(temporary)
        build_root = temporary_root / "source"
        wheel_root = temporary_root / "wheel"
        wheel_root.mkdir()
        _copy_verified_source(
            source_root,
            build_root,
            manifest,
            manifest_bytes,
            checksums_bytes,
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "--no-cache-dir",
                "--wheel-dir",
                str(wheel_root),
            ],
            cwd=build_root,
            env=environment,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise WheelBuildError(
                "BUILD_FAILED",
                "wheel build command failed; inspect the local build environment before retrying",
            )
        wheels = sorted(wheel_root.glob("*.whl"))
        if len(wheels) != 1:
            raise WheelBuildError(
                "WHEEL_SET_INVALID",
                f"expected exactly one wheel, observed {len(wheels)}",
            )
        return wheels[0].name, wheels[0].read_bytes()


def build_reproducible_wheel(source_root: Path, output_dir: Path) -> dict[str, object]:
    source_root = source_root.resolve()
    output_dir = output_dir.resolve()
    if output_dir == source_root or source_root in output_dir.parents:
        raise WheelBuildError(
            "OUTPUT_INSIDE_SOURCE",
            "transferable wheel output must be outside the sealed source tree",
        )

    environment = _build_environment()
    manifest, manifest_bytes, checksums_bytes = _verify_source_seal(source_root, environment)
    manifest_sha256 = _sha256_bytes(manifest_bytes)
    checksums_sha256 = _sha256_bytes(checksums_bytes)

    first_name, first_bytes = _build_once(
        source_root,
        environment,
        manifest,
        manifest_bytes,
        checksums_bytes,
    )
    second_name, second_bytes = _build_once(
        source_root,
        environment,
        manifest,
        manifest_bytes,
        checksums_bytes,
    )
    if first_name != second_name or first_bytes != second_bytes:
        raise WheelBuildError(
            "NON_REPRODUCIBLE_WHEEL",
            "two clean builds from the same verified source produced different wheel bytes",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / first_name
    if destination.exists():
        raise WheelBuildError(
            "OUTPUT_EXISTS",
            f"refusing to overwrite existing wheel: {destination.name}",
        )
    try:
        with destination.open("xb") as handle:
            handle.write(first_bytes)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
        raise

    return {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS",
        "artifact": {
            "name": first_name,
            "bytes": len(first_bytes),
            "sha256": _sha256_bytes(first_bytes),
        },
        "source": {
            "package_manifest_sha256": manifest_sha256,
            "checksums_sha256": checksums_sha256,
            "managed_file_count": manifest.get("managed_file_count"),
        },
        "build": {
            "rebuilds_compared": 2,
            "source_isolation": "verified-manifest-copy",
            "source_date_epoch": SOURCE_DATE_EPOCH,
            "python": platform.python_version(),
            "pip": _distribution_version("pip"),
            "setuptools": _distribution_version("setuptools"),
            "wheel": _distribution_version("wheel"),
        },
        "authority": {
            "release": False,
            "merge": False,
            "canon": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build one wheel twice from verified source bytes under a fixed ZIP epoch, "
            "publish it only if the bytes match, and emit an integrity receipt."
        )
    )
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        receipt = build_reproducible_wheel(args.source, args.output_dir)
    except WheelBuildError as exc:
        print(
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "status": "HOLD",
                    "error": {"code": exc.code, "message": str(exc)},
                    "authority": {"release": False, "merge": False, "canon": False},
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
