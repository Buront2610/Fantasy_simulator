"""Shared pytest configuration: add project root to sys.path."""

import gc
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def _collect_garbage_after_test():
    """Keep the test process memory flatter across large integration suites."""
    yield
    gc.collect()
