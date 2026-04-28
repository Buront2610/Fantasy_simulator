"""Bundled setting-bundle source paths and cached payload reads."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

BUNDLES_DIR = Path(__file__).with_name("bundles")
DEFAULT_AETHORIA_BUNDLE_PATH = BUNDLES_DIR / "aethoria.json"


@lru_cache(maxsize=1)
def default_aethoria_bundle_data() -> Dict[str, Any]:
    try:
        return json.loads(DEFAULT_AETHORIA_BUNDLE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Bundled Aethoria setting not found: {DEFAULT_AETHORIA_BUNDLE_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Bundled Aethoria setting JSON is invalid: {DEFAULT_AETHORIA_BUNDLE_PATH}: {exc.msg}"
        ) from exc
