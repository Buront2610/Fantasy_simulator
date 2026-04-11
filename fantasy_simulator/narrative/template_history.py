"""Simple template cooldown helper for narrative text generation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List


@dataclass
class TemplateHistory:
    cooldown_size: int = 4
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cooldown_size": self.cooldown_size,
            "recent": list(self._recent),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateHistory":
        history = cls(cooldown_size=int(data.get("cooldown_size", cls().cooldown_size)))
        recent: List[str] = [str(item) for item in data.get("recent", [])]
        history._recent = deque(recent[-history.cooldown_size :])
        return history
