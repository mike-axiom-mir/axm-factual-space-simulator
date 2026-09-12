from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


class InstalledPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if os.environ.get("AXM_REQUIRE_INSTALLED_PACKAGE_TESTS") != "1":
            raise unittest.SkipTest(
                "wheel consumer checks run in the dedicated installed-package workflow"
            )
        try:
            build_backend = importlib.util.find_spec("setuptools.build_meta")
        except ModuleNotFoundError:
            build_backend = None
        if build_backend is None:
            raise AssertionError("the declared setuptools wheel-build requirement is unavailable")

        cls.temporary = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.temporary.name)
        cls.build_root = cls.temp_root / "source"
        cls.wheel_root = cls.temp_root / "wheels"
        cls.venv_root = cls.temp_root / "venv"
        cls.consumer_root = cls.temp_root / "consumer"

        cls.build_root.mkdir()
        for name in ("data", "src"):
            shutil.copytree(ROOT / name, cls.build_root / name)
        for name in ("LICENSE", "README.md", "pyproject.toml"):
            shutil.copy2(ROOT / name, cls.build_root / name)

        environment = os.environ.copy()
        environment.update({
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(cls.wheel_root),
            ],
            cwd=cls.build_root,
            env=environment,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"wheel build failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        wheels = list(cls.wheel_root.glob("*.whl"))
        if len(wheels) != 1:
            raise AssertionError(f"expected one wheel, found {wheels}")
        cls.wheel = wheels[0]
        venv.EnvBuilder(with_pip=True).create(cls.venv_root)
        cls.venv_python = cls.venv_root / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        completed = subprocess.run(
            [
                str(cls.venv_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(cls.wheel),
            ],
            env=environment,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"offline wheel install failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
            )
        cls.consumer_root.mkdir()
        (cls.consumer_root / "data").mkdir()
        (cls.consumer_root / "data" / "simulation_priors.json").write_text(
            "caller data must not override packaged truth\n", encoding="utf-8"
        )
        cls.environment = environment
        cls.environment.pop("PYTHONPATH", None)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_wheel_carries_exact_canonical_resource_bytes(self) -> None:
        canonical = {
            path.relative_to(ROOT / "data").as_posix(): path.read_bytes()
            for path in (ROOT / "data").rglob("*")
            if path.is_file() and path.suffix in {".json", ".txt"}
        }
        with ZipFile(self.wheel) as archive:
            packaged = {
                name.removeprefix("axm_star_sim/data/"): archive.read(name)
                for name in archive.namelist()
                if name.startswith("axm_star_sim/data/")
                and Path(name).suffix in {".json", ".txt"}
            }
        self.assertEqual(canonical, packaged)

    def test_clean_install_runs_library_and_rejects_path_escape(self) -> None:
        program = """
from axm_star_sim.bridge_visual_core import resolve_start_package
from axm_star_sim.generator import generate_system
from axm_star_sim.migration import default_policy
from axm_star_sim.registry import data_path
from axm_star_sim.rooted_crew import load_root_kernel
from axm_star_sim.ship_blueprint import create_ship_state
from axm_star_sim.ship_interior import create_interior_state

assert generate_system('INSTALLED-LIBRARY').to_dict()
assert resolve_start_package()['schema'] == 'axm.ship-start-package.v1'
assert create_ship_state('INSTALLED-LIBRARY')['schema'] == 'axm.ship-state.v1'
assert create_interior_state('INSTALLED-LIBRARY')['schema'] == 'axm.ship-interior-state.v1'
assert load_root_kernel()
assert default_policy()['id']
try:
    data_path('../outside.json')
except ValueError:
    pass
else:
    raise AssertionError('registry path escape was accepted')
print('installed library: PASS')
"""
        result = subprocess.run(
            [str(self.venv_python), "-c", program],
            cwd=self.consumer_root,
            env=self.environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"installed library failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("installed library: PASS", result.stdout)

    def test_installed_command_shim_generates_and_verifies(self) -> None:
        script_root = self.venv_root / ("Scripts" if os.name == "nt" else "bin")
        candidates = list(script_root.glob("axm-star-sim*"))
        self.assertEqual(len(candidates), 1, candidates)
        command = candidates[0]
        first = self.consumer_root / "first"
        second = self.consumer_root / "second"
        for output in (first, second):
            generated = subprocess.run(
                [str(command), "generate", "--seed", "INSTALLED-CLI", "--output", str(output)],
                cwd=self.consumer_root,
                env=self.environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                generated.returncode,
                0,
                f"installed CLI generation failed\nstdout:\n{generated.stdout}\n"
                f"stderr:\n{generated.stderr}",
            )
            verified = subprocess.run(
                [str(command), "verify-ledger", "--output", str(output)],
                cwd=self.consumer_root,
                env=self.environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                verified.returncode,
                0,
                f"installed CLI verification failed\nstdout:\n{verified.stdout}\n"
                f"stderr:\n{verified.stderr}",
            )
            self.assertTrue(json.loads(verified.stdout)["valid"])
        first_system = json.loads((first / "system.json").read_text(encoding="utf-8"))
        second_system = json.loads((second / "system.json").read_text(encoding="utf-8"))
        first_system.pop("generated_at")
        second_system.pop("generated_at")
        self.assertEqual(first_system, second_system)

    def test_reproducible_builder_survives_source_mtime_drift_and_binds_seal(self) -> None:
        source = self.temp_root / "reproducible-source"
        source.mkdir()
        manifest_bytes = (ROOT / "PACKAGE_MANIFEST.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        for relative in manifest["files"]:
            origin = ROOT / relative
            destination = source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, destination)
        (source / "PACKAGE_MANIFEST.json").write_bytes(manifest_bytes)
        (source / "CHECKSUMS.sha256").write_bytes((ROOT / "CHECKSUMS.sha256").read_bytes())
        builder = source / "tools" / "build_reproducible_wheel.py"

        def set_mtime(timestamp: int) -> None:
            for path in source.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    os.utime(path, (timestamp, timestamp))

        def build(output: Path) -> tuple[dict[str, object], bytes]:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(builder),
                    "--source",
                    str(source),
                    "--output-dir",
                    str(output),
                ],
                cwd=self.temp_root,
                env=self.environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"reproducible wheel build failed\nstdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}",
            )
            receipt = json.loads(completed.stdout)
            self.assertEqual(receipt["schema"], "axm.reproducible-wheel-build-receipt.v1")
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["build"]["rebuilds_compared"], 2)
            self.assertEqual(receipt["build"]["source_isolation"], "verified-manifest-copy")
            artifact = output / receipt["artifact"]["name"]
            payload = artifact.read_bytes()
            self.assertEqual(len(payload), receipt["artifact"]["bytes"])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), receipt["artifact"]["sha256"])
            return receipt, payload

        set_mtime(946684800)  # 2000-01-01 UTC
        first_receipt, first_payload = build(self.temp_root / "reproducible-one")

        source_still_sealed = subprocess.run(
            [sys.executable, str(source / "tools" / "reseal_package.py"), "--check"],
            cwd=source,
            env=self.environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            source_still_sealed.returncode,
            0,
            f"builder contaminated its verified source\nstdout:\n{source_still_sealed.stdout}\n"
            f"stderr:\n{source_still_sealed.stderr}",
        )

        set_mtime(1704067200)  # 2024-01-01 UTC
        second_receipt, second_payload = build(self.temp_root / "reproducible-two")
        self.assertEqual(first_payload, second_payload)
        self.assertEqual(first_receipt["artifact"]["sha256"], second_receipt["artifact"]["sha256"])
        self.assertEqual(first_receipt["source"], second_receipt["source"])

        inside = subprocess.run(
            [
                sys.executable,
                str(builder),
                "--source",
                str(source),
                "--output-dir",
                str(source / "dist"),
            ],
            cwd=self.temp_root,
            env=self.environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(inside.returncode, 2)
        inside_hold = json.loads(inside.stderr)
        self.assertEqual(inside_hold["error"]["code"], "OUTPUT_INSIDE_SOURCE")
        self.assertFalse((source / "dist").exists())

        (source / "README.md").write_text("source drift after seal\n", encoding="utf-8")
        rejected = subprocess.run(
            [
                sys.executable,
                str(builder),
                "--source",
                str(source),
                "--output-dir",
                str(self.temp_root / "rejected-drift"),
            ],
            cwd=self.temp_root,
            env=self.environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(rejected.returncode, 2)
        hold = json.loads(rejected.stderr)
        self.assertEqual(hold["status"], "HOLD")
        self.assertEqual(hold["error"]["code"], "SOURCE_SEAL_INVALID")
        self.assertFalse((self.temp_root / "rejected-drift").exists())


if __name__ == "__main__":
    unittest.main()
