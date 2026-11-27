"""
The JSON a service carries in its on-chain ``description``.

When the agent registers a service it writes, instead of free text:

    {"v": 1, "robot": "panther", "summary": "...",
     "params": {"pickup":  {"type": "place", "label": "Pick-up place"},
                "dropoff": {"type": "place", "label": "Deliver to"}},
     "places": {"samuel_desk": {"label": "Samuel's desk", "xy": [1.2, 3.4]}},
     "settings": {"wait_s": 60}}

This makes the chain the single source both org-web (to render the task form)
and the oracle (to check poses against places) read from, with no robot-specific
configuration of their own. ``places`` is only included when the service has a
place parameter; the executor-specific ``waypoint`` names are not published.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from rodeo_common.services_config import PARAM_TYPES, RobotConfig, ServiceSpec

FORMAT_VERSION = 1


@dataclass
class ServiceDescription:
    robot: str = ""
    summary: str = ""
    params: dict = field(default_factory=dict)     # name -> {"type", "label", "optional"}
    places: dict = field(default_factory=dict)     # id -> {"label", "xy"}
    settings: dict = field(default_factory=dict)
    structured: bool = False
    version: int = 0


def _param_json(p) -> dict:
    d = {"type": p.type, "label": p.label, "optional": p.optional}
    if p.default is not None:
        d["default"] = p.default
    return d


def build_service_description(robot: RobotConfig, service: ServiceSpec) -> dict:
    d = {
        "v": FORMAT_VERSION,
        "robot": robot.robot,
        "summary": service.summary,
        "params": {p.name: _param_json(p) for p in service.params.values()},
        "settings": service.settings,
    }
    if service.place_params:
        d["places"] = {pid: {"label": pl.label, "xy": pl.xy} for pid, pl in robot.places.items()}
    return d


def encode_service_description(robot: RobotConfig, service: ServiceSpec) -> str:
    return json.dumps(build_service_description(robot, service),
                      separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def parse_service_description(text: str | None) -> ServiceDescription:
    """Free text (e.g. services registered before this convention) parses as unstructured."""
    try:
        d = json.loads(text or "")
    except (ValueError, TypeError):
        d = None
    if not (isinstance(d, dict) and isinstance(d.get("v"), int)):
        return ServiceDescription(summary=text or "", structured=False)
    params = d.get("params") or {}
    places = d.get("places") or {}
    return ServiceDescription(
        robot=str(d.get("robot", "")), summary=str(d.get("summary", "")),
        params=params if isinstance(params, dict) else {},
        places=places if isinstance(places, dict) else {},
        settings=d.get("settings") if isinstance(d.get("settings"), dict) else {},
        structured=True, version=d["v"])


def resolve_task_params(schema: ServiceDescription, params: dict) -> tuple:
    """(params with schema defaults filled in, problems). Problems empty means valid."""
    if not isinstance(params, dict):
        return {}, ["parameters must be a JSON object"]
    resolved = dict(params)
    for name, spec in schema.params.items():
        if resolved.get(name) in (None, "") and spec.get("default") is not None:
            resolved[name] = spec["default"]
    return resolved, validate_task_params(schema, resolved)


def validate_task_params(schema: ServiceDescription, params: dict) -> list:
    """Problems with ``params`` against a service's schema; an empty list means valid."""
    errors = []
    if not isinstance(params, dict):
        return ["parameters must be a JSON object"]
    for name, spec in schema.params.items():
        typ, optional = spec.get("type"), bool(spec.get("optional", False))
        if name not in params or params[name] in (None, ""):
            if not optional:
                errors.append(f"missing parameter '{name}'")
            continue
        v = params[name]
        if typ == "place":
            if not isinstance(v, str) or v not in schema.places:
                errors.append(f"'{name}': unknown place '{v}'")
        elif typ == "number":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                errors.append(f"'{name}': expected a number, got {v!r}")
        elif typ == "text":
            if not isinstance(v, str):
                errors.append(f"'{name}': expected text, got {v!r}")
        elif typ not in PARAM_TYPES:
            errors.append(f"'{name}': schema has unknown type '{typ}'")
    for name in params:
        if name not in schema.params:
            errors.append(f"unexpected parameter '{name}'")
    return errors
