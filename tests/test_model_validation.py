from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class ModelValidationTests(unittest.TestCase):
    def test_canonical_model_validates(self):
        process = subprocess.run(
            [sys.executable, str(PROJECT / "scripts/validate_model.py"), str(PROJECT)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertIn('"broken_references": 0', process.stdout)


if __name__ == "__main__":
    unittest.main()
