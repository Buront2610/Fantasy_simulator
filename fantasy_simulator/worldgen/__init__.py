"""World-generation proof-of-concept helpers.

This package intentionally stays lightweight and stdlib-only so the repo can
experiment with generated terrain without committing the main simulation loop
to a single generation strategy yet.
"""

from .generator import (
    GeneratedWorld,
    WorldgenConfig,
    build_ascii_preview,
    generate_world,
)
from .types import SiteCandidate

__all__ = [
    "GeneratedWorld",
    "SiteCandidate",
    "WorldgenConfig",
    "build_ascii_preview",
    "generate_world",
]
