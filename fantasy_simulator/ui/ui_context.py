"""
ui_context.py - Dependency container for the UI layer.

``UIContext`` bundles an ``InputBackend`` and ``RenderBackend`` together
so that all screen functions receive a single injection point.  When no
context is supplied, factory defaults are used (prompt_toolkit / Rich when
available, otherwise ``StdInputBackend`` + ``PrintRenderBackend``), so
existing callers keep working while richer backends are auto-selected.

Example (production)::

    ctx = UIContext()                         # uses stdin/stdout
    screen_new_simulation(ctx=ctx)

Example (testing)::

    ctx = UIContext(inp=RecordingInput(...), out=BufferOutput())
    screen_new_simulation(ctx=ctx)
    assert "world_created" in ctx.out.lines
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .input_backend import InputBackend, create_default_input_backend
from .render_backend import RenderBackend, create_default_render_backend


class UIContext:
    """Thin wrapper around an input backend and a render backend.

    All screen / menu functions accept an optional ``ctx`` parameter.
    If ``None`` is passed they create a default ``UIContext`` internally,
    so the change is fully backward-compatible.

    ``choose_key()`` is the orchestrating facade that separates rendering
    (delegated to ``self.out``) from reading (delegated to ``self.inp``),
    so swapping either backend independently works as expected.
    """

    __slots__ = ("inp", "out")

    def __init__(
        self,
        inp: InputBackend | None = None,
        out: RenderBackend | None = None,
    ) -> None:
        self.inp: InputBackend = inp or create_default_input_backend()
        self.out: RenderBackend = out or create_default_render_backend()

    def choose_key(
        self,
        prompt: str,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> str:
        """Render a numbered menu then read and return the selected key.

        Rendering goes through ``self.out.print_menu()``; reading goes through
        ``self.inp.read_menu_key()``.  The two responsibilities are fully
        separated so any combination of backends works correctly.
        """
        self.out.print_menu(prompt, key_label_pairs, default)
        return self.inp.read_menu_key(key_label_pairs, default)


def _default_ctx(ctx: UIContext | None) -> UIContext:
    """Return *ctx* if provided, or a fresh default ``UIContext``."""
    if ctx is not None:
        return ctx
    return UIContext()
