"""
Validators, chosen by the task's (category, task_type).

A validator is a function ``validate(ctx) -> Verdict`` registered with
``@register("Category", "TaskType")``. Adding a validator for a new service
(TIAGo's tour, the drone patrol) means adding a module here and importing it
below; the oracle core does not change.
"""
from __future__ import annotations

from dataclasses import dataclass, field

_REGISTRY: dict = {}


@dataclass
class Verdict:
    ok: bool
    reason: str = ""                                 # on-chain rejection reason (<= 128 chars)
    lines: list = field(default_factory=list)        # human-readable summary

    def check(self, ok: bool, line: str, reason: str = "") -> bool:
        self.lines.append(("  OK    " if ok else "  FAIL  ") + line)
        if not ok and self.ok:
            self.ok, self.reason = False, (reason or line)
        return ok


def register(category: str, task_type: str):
    def deco(fn):
        _REGISTRY[(category, task_type)] = fn
        return fn
    return deco


def validator_for(category: str, task_type: str):
    return _REGISTRY.get((category, task_type))


def registered() -> list:
    return sorted(f"{c}/{t}" for c, t in _REGISTRY)


from . import charging  # noqa: E402,F401  (registers Energy/Charging)
from . import delivery  # noqa: E402,F401  (registers Logistics/ItemTransport)
