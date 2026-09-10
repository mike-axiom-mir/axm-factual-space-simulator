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


RECEIPT_SCHEMA = "axm.reproducible-wheel-build-receipt.v1"
SOURCE_DATE_EPOCH = 315532800  # 1980-01-01T00:00:00Z, the ZIP format floor.


class WheelBuildError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _verify_source_seal(source_root: Path, environment: dict[str, str]) -> tuple[str, str]:
    manifest = source_root / "PACKAGE_MANIFEST.json"
    checksums = source_root / "CHECKSUMS.sha256"
    sealer = source_root / "tools" / "reseal_package.py"
    for required in (manifest, checksums, sealer, source_root / "pyproject.toml"):
        if not required.is_file():
            raise WheelBuildError(
                "SOURCE_SEAL_INVALID",
                f"required verified-source file is missing: {required.name}",
            )

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
    return _sha256_file(manifest), _sha256_file(checksums)


def _build_once(source_root: Path, environment: dict[str, str]) -> tuple[str, bytes]:
    with tempfile.TemporaryDirectory(prefix="axm-wheel-build-") as temporary:
        wheel_root = Path(temporary)
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
            cwd=source_root,
            env=environment,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise WheelBuildError(
                "BUILD_FAILED",
                "wheel build command failed; inspect the local build output before retrying",
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
    environment = _build_environment()
    manifest_sha256, checksums_sha256 = _verify_source_seal(source_root, environment)

    first_name, first_bytes = _build_once(source_root, environment)
    second_name, second_bytes = _build_once(source_root, environment)
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
        },
        "build": {
            "rebuilds_compared": 2,
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
            "Build one wheel twice from a verified source tree under a fixed ZIP epoch, "
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
