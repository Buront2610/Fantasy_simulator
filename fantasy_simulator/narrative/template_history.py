"""Simple template cooldown helper for narrative text generation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable


@dataclass
class TemplateHistory:
    cooldown_size: int = 3
    _recent: Deque[str] = field(default_factory=deque)

    def choose(self, candidates: Iterable[str]) -> str:
        pool = list(candidates)
        if not pool:
            return ""
        for key in pool:
            if key not in self._recent:
                self.record(key)
                return key
        chosen = pool[0]
        self.record(chosen)
        return chosen

    def record(self, key: str) -> None:
        self._recent.append(key)
        while len(self._recent) > self.cooldown_size:
            self._recent.popleft()
