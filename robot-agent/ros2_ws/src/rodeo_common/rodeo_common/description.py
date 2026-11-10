"""
Task description convention.

A task's on-chain ``description`` is a JSON object written by org-web:

    {"v": 1, "params": {"pickup": "package_pickup", "dropoff": "samuel_desk",
                        "sender": "Farah", "recipient": "Samuel"},
     "note": "fragile"}

``params`` follows the parameter schema of the service the task is for (see
service_description.py); fixed services (tour, security) have ``{}``. ``note``
is the creator's free text.

Anything that is not such an object - including every task created before this
convention - parses as a free-text note with no parameters, so old tasks and
hand-written ones keep working.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

FORMAT_VERSION = 1


@dataclass
class TaskDescription:
    params: dict = field(default_factory=dict)
    note: str = ""
    structured: bool = False      # False: free text, not the JSON convention
    version: int = 0


def encode_task_description(params: dict | None = None, note: str = "") -> str:
    if params is not None and not isinstance(params, dict):
        raise TypeError("params must be a dict")
    return json.dumps({"v": FORMAT_VERSION, "params": params or {}, "note": note or ""},
                      separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def parse_task_description(text: str | None) -> TaskDescription:
    text = text or ""
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        d = None
    if (isinstance(d, dict) and isinstance(d.get("v"), int)
            and isinstance(d.get("params", {}), dict)):
        note = d.get("note", "")
        return TaskDescription(params=dict(d.get("params", {})),
                               note=note if isinstance(note, str) else str(note),
                               structured=True, version=d["v"])
    return TaskDescription(params={}, note=text, structured=False, version=0)
