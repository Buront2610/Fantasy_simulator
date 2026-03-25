"""
input_backend.py - Abstract input interface for the CLI.

Defines ``InputBackend`` so that the actual input mechanism (builtin
``input()``, prompt_toolkit, Textual widgets, …) can be swapped without
touching presentation or domain code.
"""

from __future__ import annotations

import os
from typing import List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class InputBackend(Protocol):
    """Minimal contract every input provider must satisfy."""

    def read_line(self, prompt: str = "") -> str:
        """Read a single line of text from the user."""
        ...  # pragma: no cover

    def read_menu_key(
        self,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> str:
        """Read and validate a menu selection, return the corresponding key.

        Assumes the menu options have already been rendered by
        ``RenderBackend.print_menu()``.  *key_label_pairs* is
        ``[(key, display_label), ...]``; *default* is a 1-based index string.
        """
        ...  # pragma: no cover

    def pause(self, message: str = "") -> None:
        """Wait for the user to press Enter."""
        ...  # pragma: no cover


class StdInputBackend:
    """Default backend that delegates to Python's builtin ``input()``."""

    def read_line(self, prompt: str = "") -> str:
        return input(prompt)

    def read_menu_key(
        self,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> str:
        from .ui_helpers import _read_menu_choice
        return _read_menu_choice(key_label_pairs, default)

    def pause(self, message: str = "") -> None:
        from .ui_helpers import _pause
        _pause(message)


class PromptToolkitInputBackend(StdInputBackend):
    """Input backend that uses prompt_toolkit when available."""

    def __init__(self) -> None:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import InMemoryHistory

        self._session = PromptSession(history=InMemoryHistory())

    def read_line(self, prompt: str = "") -> str:
        return self._session.prompt(prompt)

    def read_menu_key(
        self,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> str:
        from ..i18n import tr
        try:
            from prompt_toolkit.completion import WordCompleter
            from prompt_toolkit.validation import Validator
        except Exception:
            WordCompleter = None  # type: ignore[assignment]
            Validator = None  # type: ignore[assignment]

        labels = [str(i) for i in range(1, len(key_label_pairs) + 1)]
        completer = WordCompleter(labels, ignore_case=False) if WordCompleter else None
        prompt = f"  {tr('your_choice')}: "

        def _resolve(raw_text: str) -> Optional[str]:
            raw = raw_text.strip()
            if not raw and default is not None and default.isdigit():
                idx = int(default) - 1
                if 0 <= idx < len(key_label_pairs):
                    return key_label_pairs[idx][0]
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(key_label_pairs):
                    return key_label_pairs[idx][0]
            return None

        validator = None
        if Validator is not None:
            validator = Validator.from_callable(
                lambda text: _resolve(text) is not None,
                error_message=tr("invalid_choice"),
                move_cursor_to_end=True,
            )

        while True:
            raw = self._session.prompt(
                prompt,
                completer=completer,
                validator=validator,
                validate_while_typing=False,
            )
            resolved = _resolve(raw)
            if resolved is not None:
                return resolved

    def pause(self, message: str = "") -> None:
        self.read_line(message or "")


def create_default_input_backend() -> InputBackend:
    """Return default input backend.

    Default is ``StdInputBackend`` for reproducibility.  Set
    ``FANTASY_SIMULATOR_INPUT_BACKEND=prompt_toolkit`` to opt in.
    """
    selected = os.getenv("FANTASY_SIMULATOR_INPUT_BACKEND", "").strip().lower()
    if selected in {"", "std", "stdin"}:
        return StdInputBackend()
    if selected not in {"prompt_toolkit", "prompt"}:
        return StdInputBackend()
    try:
        return PromptToolkitInputBackend()
    except (ImportError, ModuleNotFoundError):
        return StdInputBackend()
