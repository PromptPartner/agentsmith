#!/usr/bin/env python3
"""Evidence classification regressions; no provider requests."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('containment', Path(__file__).with_name('qualification-containment.py'))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ContainmentTests(unittest.TestCase):
    def test_provider_failure_does_not_prove_denial(self):
        self.assertEqual(MODULE.classify_denial(1, 'provider authentication failed', True, True), 'undetermined')

    def test_missing_control_does_not_prove_denial(self):
        self.assertEqual(MODULE.classify_denial(1, 'PermissionError: Operation not permitted', True, False), 'undetermined')

    def test_actual_permission_denial_and_control(self):
        self.assertEqual(MODULE.classify_denial(1, 'PermissionError: Operation not permitted', True, True), 'pass')

    def test_changed_sentinel_is_failure(self):
        self.assertEqual(MODULE.classify_denial(1, 'PermissionError: Operation not permitted', False, True), 'fail')

    def test_output_is_immutable(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'evidence'
            MODULE.initialize_output(path)
            with self.assertRaises(FileExistsError):
                MODULE.initialize_output(path)

    def test_temporary_output_cannot_claim_outside_temp_layout(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                MODULE.require_outside_temporary(Path(root)/'evidence')

    def test_snapshot_detects_replacement_with_equal_content(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'sentinel'
            path.write_text('original')
            before = MODULE.snapshot(path)
            replacement = Path(root)/'replacement'
            replacement.write_text('original')
            replacement.replace(path)
            self.assertNotEqual(before, MODULE.snapshot(path))


if __name__ == '__main__':
    unittest.main()
