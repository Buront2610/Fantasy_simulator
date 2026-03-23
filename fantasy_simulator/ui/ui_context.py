"""
ui_context.py - Dependency container for the UI layer.

``UIContext`` bundles an ``InputBackend`` and ``RenderBackend`` together
so that all screen functions receive a single injection point.  When no
context is supplied, the default (``StdInputBackend`` + ``PrintRenderBackend``)
is used — meaning existing callers see zero behaviour change.

Example (production)::

    ctx = UIContext()                         # uses stdin/stdout
    screen_new_simulation(ctx=ctx)

Example (testing)::

    ctx = UIContext(inp=RecordingInput(...), out=BufferOutput())
    screen_new_simulation(ctx=ctx)
    assert "world_created" in ctx.out.lines
"""

from __future__ import annotations

from .input_backend import InputBackend, StdInputBackend
from .render_backend import RenderBackend, PrintRenderBackend


class UIContext:
    """Thin wrapper around an input backend and a render backend.

    All screen / menu functions accept an optional ``ctx`` parameter.
    If ``None`` is passed they create a default ``UIContext`` internally,
    so the change is fully backward-compatible.
    """

    __slots__ = ("inp", "out")

    def __init__(
        self,
        inp: InputBackend | None = None,
        out: RenderBackend | None = None,
    ) -> None:
        self.inp: InputBackend = inp or StdInputBackend()
        self.out: RenderBackend = out or PrintRenderBackend()


def _default_ctx(ctx: UIContext | None) -> UIContext:
    """Return *ctx* if provided, or a fresh default ``UIContext``."""
    if ctx is not None:
        return ctx
    return UIContext()
