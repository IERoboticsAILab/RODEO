"""
Task description convention.

A task's on-chain ``description`` is a JSON object written by org-web:

    {"v": 1, "title": "Parcel for Samuel",
     "params": {"pickup": "package_pickup", "dropoff": "samuel_desk",
                "sender": "Farah", "recipient": "Samuel"},
     "note": "fragile"}

Every task has the same base: ``title`` (its name; the contract has no field
for it), ``note`` (the creator's free text), and the contract's own category,
task type and reward. ``params`` are the service-specific details and follow the
parameter schema of the service the task is for (see service_description.py);
fixed services (tour, security) have ``{}``. ``title`` is left out when empty.

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
    title: str = ""
    structured: bool = False      # False: free text, not the JSON convention
    version: int = 0


def encode_task_description(params: dict | None = None, note: str = "", title: str = "") -> str:
    if params is not None and not isinstance(params, dict):
        raise TypeError("params must be a dict")
    d = {"v": FORMAT_VERSION, "params": params or {}, "note": note or ""}
    if title:
        d["title"] = title
    return json.dumps(d, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def parse_task_description(text: str | None) -> TaskDescription:
    text = text or ""
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        d = None
    if (isinstance(d, dict) and isinstance(d.get("v"), int)
            and isinstance(d.get("params", {}), dict)):
        note, title = d.get("note", ""), d.get("title", "")
        return TaskDescription(params=dict(d.get("params", {})),
                               note=note if isinstance(note, str) else str(note),
                               title=title if isinstance(title, str) else str(title),
                               structured=True, version=d["v"])
    return TaskDescription(params={}, note=text, structured=False, version=0)
