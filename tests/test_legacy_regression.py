"""Pytest wrapper around the legacy tests.py regression gate.

Runs the full legacy suite (each test independently, in fresh processes) and
asserts the 35-pass / 4-known-fail / 0-new-regression baseline. Marked ``slow``
because it spawns ~39 subprocesses, each importing the 12k-line module; opt out
with ``-m "not slow"`` during fast iteration.
"""

import pytest

from regression_gate import EXPECTED_FAIL, EXPECTED_PASS, run_gate


@pytest.mark.slow
def test_legacy_suite_baseline():
    result = run_gate(verbose=True)
    assert result["passed"] == EXPECTED_PASS
    assert result["failed"] == EXPECTED_FAIL
    assert result["new_failures"] == []
    assert result["unexpected_passes"] == []
