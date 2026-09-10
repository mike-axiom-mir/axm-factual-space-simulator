from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


class InstalledPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.temp_root = Path(cls.temporary.name)
        cls.build_root = cls.temp_root / "source"
        cls.wheel_root = cls.temp_root / "wheels"
        cls.site_root = cls.temp_root / "site"
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
        subprocess.run(
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
            check=True,
            capture_output=True,
            text=True,
        )
        wheels = list(cls.wheel_root.glob("*.whl"))
        if len(wheels) != 1:
            raise AssertionError(f"expected one wheel, found {wheels}")
        cls.wheel = wheels[0]
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--target",
                str(cls.site_root),
                str(cls.wheel),
            ],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.consumer_root.mkdir()
        (cls.consumer_root / "data").mkdir()
        (cls.consumer_root / "data" / "simulation_priors.json").write_text(
            "caller data must not override packaged truth\n", encoding="utf-8"
        )
        cls.environment = environment
        cls.environment["PYTHONPATH"] = str(cls.site_root)

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
            [sys.executable, "-c", program],
            cwd=self.consumer_root,
            env=self.environment,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("installed library: PASS", result.stdout)

    def test_installed_command_shim_generates_and_verifies(self) -> None:
        script_root = self.site_root / ("Scripts" if os.name == "nt" else "bin")
        candidates = list(script_root.glob("axm-star-sim*"))
        self.assertEqual(len(candidates), 1, candidates)
        command = candidates[0]
        first = self.consumer_root / "first"
        second = self.consumer_root / "second"
        for output in (first, second):
            subprocess.run(
                [str(command), "generate", "--seed", "INSTALLED-CLI", "--output", str(output)],
                cwd=self.consumer_root,
                env=self.environment,
                check=True,
                capture_output=True,
                text=True,
            )
            verified = subprocess.run(
                [str(command), "verify-ledger", "--output", str(output)],
                cwd=self.consumer_root,
                env=self.environment,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue(json.loads(verified.stdout)["valid"])
        first_system = json.loads((first / "system.json").read_text(encoding="utf-8"))
        second_system = json.loads((second / "system.json").read_text(encoding="utf-8"))
        first_system.pop("generated_at")
        second_system.pop("generated_at")
        self.assertEqual(first_system, second_system)


if __name__ == "__main__":
    unittest.main()
