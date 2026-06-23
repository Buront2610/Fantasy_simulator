"""Shared UI test doubles for screen/backend integration tests."""

from __future__ import annotations

import shutil


class RecordingRenderBackend:
    """Captures UI output as both structured calls and plain rendered lines."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.lines: list[str] = []

    def print_line(self, text: str = "") -> None:
        self.calls.append(("print_line", text))
        self.lines.append(text)

    def print_heading(self, text: str) -> None:
        self.calls.append(("print_heading", text))
        self.lines.append(text)

    def print_separator(self, char: str = "=", width: int = 62) -> None:
        self.calls.append(("print_separator", char, str(width)))
        self.lines.append(f"{char * width}")

    def print_error(self, text: str) -> None:
        self.calls.append(("print_error", text))
        self.lines.append(text)

    def print_success(self, text: str) -> None:
        self.calls.append(("print_success", text))
        self.lines.append(text)

    def print_warning(self, text: str) -> None:
        self.calls.append(("print_warning", text))
        self.lines.append(text)

    def print_wrapped(self, text: str, indent: int = 4) -> None:
        self.calls.append(("print_wrapped", text))
        self.lines.append(text)

    def print_dim(self, text: str) -> None:
        self.calls.append(("print_dim", text))
        self.lines.append(text)

    def print_highlighted(self, text: str) -> None:
        self.calls.append(("print_highlighted", text))
        self.lines.append(text)

    def format_status(self, text: str, positive: bool) -> str:
        return text

    def print_menu(self, prompt: str, key_label_pairs, default=None) -> None:
        self.calls.append(("print_menu", prompt, len(key_label_pairs)))
        self.lines.append(prompt)

    def print_panel(self, title: str, text: str) -> None:
        self.calls.append(("print_panel", title, text))
        self.lines.append(title)
        self.lines.append(text)

    def get_terminal_width(self) -> int:
        return shutil.get_terminal_size(fallback=(80, 24)).columns

    @property
    def text(self) -> str:
        return "\n".join(str(part) for (_, *rest) in self.calls for part in rest)


class ScriptedInputBackend:
    """Returns scripted answers to read_line / choose_key / pause."""

    def __init__(
        self,
        answers: list[str] | None = None,
        menu_keys: list[str] | None = None,
    ) -> None:
        self._answers = list(answers or [])
        self._menu_keys = list(menu_keys or [])
        self._answer_idx = 0
        self._menu_idx = 0

    def read_line(self, prompt: str = "") -> str:
        if self._answer_idx < len(self._answers):
            value = self._answers[self._answer_idx]
            self._answer_idx += 1
            return value
        return ""

    def read_menu_key(self, key_label_pairs, default=None) -> str:
        if self._menu_idx < len(self._menu_keys):
            value = self._menu_keys[self._menu_idx]
            self._menu_idx += 1
            return value
        return key_label_pairs[-1][0]

    def pause(self, message: str = "") -> None:
        return None
