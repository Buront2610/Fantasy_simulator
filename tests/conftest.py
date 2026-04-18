"""Shared pytest configuration: add project root to sys.path."""

import gc
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_GC_INTERVAL = 50
_tests_since_gc = 0


def pytest_runtest_teardown(item, nextitem):  # type: ignore[no-untyped-def]
    """Collect cyclic garbage periodically without taxing every single test."""
    global _tests_since_gc
    _tests_since_gc += 1
    if _tests_since_gc >= _GC_INTERVAL:
        gc.collect()
        _tests_since_gc = 0


def pytest_sessionfinish(session, exitstatus):  # type: ignore[no-untyped-def]
    gc.collect()
