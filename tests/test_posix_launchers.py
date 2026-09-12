import os
import stat
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "POSIX executable bits are not meaningful on Windows")
class PosixLauncherTests(unittest.TestCase):
    def test_shell_entrypoints_are_executable(self) -> None:
        launchers = sorted(ROOT.rglob("*.sh"))
        self.assertTrue(launchers, "expected at least one POSIX shell entrypoint")

        missing = [
            path.relative_to(ROOT).as_posix()
            for path in launchers
            if not path.stat().st_mode & stat.S_IXUSR
        ]
        self.assertEqual([], missing, f"shell entrypoints missing owner execute permission: {missing}")


if __name__ == "__main__":
    unittest.main()
