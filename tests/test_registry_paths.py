import os
import tempfile
import unittest
from pathlib import Path

from axm_star_sim import registry


class RegistryPathTests(unittest.TestCase):
    def test_canonical_data_is_resolved_independently_of_cwd(self):
        expected_root = registry.PACKAGE_ROOT / "data"
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            try:
                os.chdir(temp)
                source_path = registry.data_path("source_registry.json")
                formula_path = registry.data_path("formula_registry.json")
                priors_path = registry.data_path("simulation_priors.json")

                self.assertEqual(source_path, expected_root / "source_registry.json")
                self.assertEqual(formula_path, expected_root / "formula_registry.json")
                self.assertEqual(priors_path, expected_root / "simulation_priors.json")
                self.assertTrue(registry.load_source_registry())
                self.assertTrue(registry.load_formula_registry())
                self.assertTrue(registry.load_priors())
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
