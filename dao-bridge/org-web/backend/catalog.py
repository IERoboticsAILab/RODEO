"""
The task form's catalog: what can be ordered right now, built from the
services on chain.

    GET /catalog -> one entry per (category, task type) offered by an active
                    service, with the cheapest price, how many providers are
                    free, and the parameter schema and places from that
                    provider's on-chain description (RODEO v2 services).

Rules, matching what the contract will do with the task:
  * inactive services are left out (offline robots);
  * busy-only kinds are listed with free == 0: a task waits on chain until a
    provider is free;
  * the schema comes from the provider the contract would pick: the cheapest
    free one, else the cheapest;
  * services whose description settings say "robot_only": true (charging) are
    left out: only robots order them, through their agents.

The description conventions come from rodeo_common (robot-agent/), shared
with the robot agents and the oracle, so the form, the robots and the oracle
agree on parameters, defaults and places.
"""
from __future__ import annotations

import os
import sys

try:
    from rodeo_common.description import encode_task_description
    from rodeo_common.service_description import parse_service_description, resolve_task_params
except ImportError:                                   # running from a source checkout
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..",
                                    "robot-agent", "ros2_ws", "src", "rodeo_common"))
    from rodeo_common.description import encode_task_description
    from rodeo_common.service_description import parse_service_description, resolve_task_params

WEI = 10 ** 18


def build_catalog(services: list) -> list:
    """``services`` as returned by org_code.list_all_services()."""
    groups: dict = {}
    for s in services:
        if s["active"]:
            groups.setdefault((s["serviceCategory"], s["serviceType"]), []).append(s)
    catalog = []
    for (category, task_type), rows in sorted(groups.items()):
        free = [s for s in rows if not s["busy"]]
        pick = min(free or rows, key=lambda s: (int(s["priceWei"]), s["id"]))
        schema = parse_service_description(pick["description"])
        if schema.settings.get("robot_only"):
            continue
        cheapest = min(int(s["priceWei"]) for s in rows)
        catalog.append({
            "key": f"{category}/{task_type}",
            "category": category,
            "taskType": task_type,
            "name": pick["name"],
            "summary": schema.summary if schema.structured else pick["description"],
            "robot": schema.robot,
            "structured": schema.structured,
            "minPriceWei": str(cheapest),
            "minPriceIec": cheapest / WEI,
            "pickPriceIec": int(pick["priceWei"]) / WEI,
            "providers": len(rows),
            "free": len(free),
            "params": schema.params,      # name -> {type, label, optional, default?}
            "places": {pid: {"label": p.get("label", pid)} for pid, p in schema.places.items()},
        })
    return catalog


def find(catalog: list, category: str, task_type: str):
    for entry in catalog:
        if entry["category"] == category and entry["taskType"] == task_type:
            return entry
    return None


def task_description(services: list, category: str, task_type: str, params, note: str,
                     title: str = "") -> str:
    """
    The description to post for a task. Without ``params`` it is the note as
    free text (the old form). With ``params`` (``{}`` for a service without
    details) they are checked against the schema of the service the contract
    would pick, and written in the RODEO convention with the title and note;
    raises ValueError with the problems otherwise.
    """
    if params is None:
        return note
    entry = find(build_catalog(services), category, task_type)
    if entry is None:
        raise ValueError(f"no active service offers {category}/{task_type}")
    if entry["structured"]:
        schema = parse_service_description(_pick(services, category, task_type)["description"])
        _, errors = resolve_task_params(schema, params)
        if errors:
            raise ValueError("; ".join(errors))
    elif params:
        raise ValueError(f"{category}/{task_type} takes no parameters")
    return encode_task_description(params, note, title.strip())


def _pick(services, category, task_type):
    rows = [s for s in services if s["active"] and (s["serviceCategory"], s["serviceType"]) == (category, task_type)]
    free = [s for s in rows if not s["busy"]]
    return min(free or rows, key=lambda s: (int(s["priceWei"]), s["id"]))
