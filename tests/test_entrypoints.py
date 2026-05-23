"""Entrypoint smoke tests — verify both CLI launch routes start cleanly.

These tests use subprocess to invoke each entry point and confirm that
the Python process starts, imports succeed, and the application exits
without errors when given immediate input to quit.
"""

from __future__ import annotations

import subprocess
import sys
from importlib import import_module
from pathlib import Path

# Project root is on sys.path via conftest.py, but the subprocess
# must run from the project root so that `main.py` and the
# `fantasy_simulator` package are both importable.
_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = str(_PROJECT_ROOT_PATH)


class TestEntrypointSmoke:
    """Both ``python -m fantasy_simulator`` and ``python main.py`` must
    start without import errors and exit cleanly when told to quit."""

    @staticmethod
    def _run_entrypoint(args: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess:
        """Run *args* as a subprocess, feed '6' (exit) on stdin, return result."""
        return subprocess.run(
            [sys.executable, *args],
            input="6\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=_PROJECT_ROOT,
            timeout=timeout,
        )

    def test_python_m_fantasy_simulator_starts_and_exits(self) -> None:
        """``python -m fantasy_simulator`` smoke test."""
        result = self._run_entrypoint(["-m", "fantasy_simulator"])
        # The process should have reached the menu and printed something.
        assert result.stdout, "No stdout produced — import or startup failure"
        # Exit code 0 is expected from the normal "exit" menu choice.
        assert result.returncode == 0, (
            f"Non-zero exit code {result.returncode}.\n"
            f"stderr:\n{result.stderr}"
        )

    def test_python_main_py_starts_and_exits(self) -> None:
        """``python main.py`` (compatibility wrapper) smoke test."""
        result = self._run_entrypoint(["main.py"])
        assert result.stdout, "No stdout produced — import or startup failure"
        assert result.returncode == 0, (
            f"Non-zero exit code {result.returncode}.\n"
            f"stderr:\n{result.stderr}"
        )

    def test_python_m_produces_menu_header(self) -> None:
        """The package entrypoint should display the FANTASY SIMULATOR header."""
        result = self._run_entrypoint(["-m", "fantasy_simulator"])
        assert "FANTASY SIMULATOR" in result.stdout

    def test_main_py_produces_menu_header(self) -> None:
        """The compatibility wrapper should display the same header."""
        result = self._run_entrypoint(["main.py"])
        assert "FANTASY SIMULATOR" in result.stdout

    def test_package_importable(self) -> None:
        """``import fantasy_simulator`` must succeed without side-effects."""
        result = subprocess.run(
            [sys.executable, "-c", "import fantasy_simulator"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=_PROJECT_ROOT,
            timeout=10,
        )
        assert result.returncode == 0, (
            f"Failed to import package.\nstderr:\n{result.stderr}"
        )

    def test_console_script_entry_points_resolve_to_callable_wrapper(self) -> None:
        """Declared console scripts should call the package wrapper, not bypass it."""
        pyproject = (_PROJECT_ROOT_PATH / "pyproject.toml").read_text(encoding="utf-8")

        for script_name in ("fantasy-simulator", "fantasy-sim"):
            expected = f'{script_name} = "fantasy_simulator.__main__:main"'
            assert expected in pyproject
            module_name, function_name = "fantasy_simulator.__main__", "main"
            module = import_module(module_name)
            assert getattr(module, function_name) is module.main

    def test_console_script_wrapper_handles_keyboard_interrupt(self) -> None:
        """The callable used by console scripts should preserve Ctrl-C exit behavior."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "\n".join([
                    "from unittest.mock import patch",
                    "import fantasy_simulator.__main__ as m",
                    "with patch.object(m, '_main', side_effect=KeyboardInterrupt):",
                    "    m.main()",
                ]),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=_PROJECT_ROOT,
            timeout=10,
        )

        assert result.returncode == 130
        assert result.stdout.strip()
