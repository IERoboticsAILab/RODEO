"""
Delivery validator (Logistics / ItemTransport).

Checks, against the task's parameters and the places in the service's on-chain
description:

    route    the robot arrived at the pick-up place and then at the drop-off
             place, and its recorded pose at each arrival was within
             DELIVERY_PLACE_RADIUS_M of that place
    load     stable deck readings: empty before pick-up, at least
             DELIVERY_MIN_PACKAGE_KG added at pick-up, still loaded on arrival at
             drop-off, empty again after drop-off (all within DELIVERY_WEIGHT_TOL_KG);
             matches declared_weight_kg if the task gave one

No recipient confirmation is required: unloading at the drop-off place (deck
weight falls) is the evidence of delivery. CONFIRM events, if any, are ignored.

What an executor must record for this to pass: ARRIVE/DEPART events with place
ids, poses while moving and at stops, stable weight readings at the start, at
pick-up after loading, and at drop-off before and after unloading.
"""
from __future__ import annotations

import os
import statistics

from rodeo_common.service_description import parse_service_description

from ..proofs import distance, nearest_pose
from . import Verdict, register


def _f(name, default):
    return float(os.environ.get(name, default))


def _stable(proof, t0=float("-inf"), t1=float("inf")):
    return [kg for t, kg, stable in proof.weights if stable and t0 <= t <= t1]


def _first_event(proof, type_, place, after=float("-inf")):
    for e in proof.events:
        if e.type == type_ and e.place == place and e.t >= after:
            return e
    return None


@register("Logistics", "ItemTransport")
def validate(ctx) -> Verdict:
    radius = _f("DELIVERY_PLACE_RADIUS_M", "1.0")
    tol = _f("DELIVERY_WEIGHT_TOL_KG", "0.1")
    min_pkg = _f("DELIVERY_MIN_PACKAGE_KG", "0.05")
    proof, v = ctx.proof, Verdict(ok=True)

    params = proof.params
    pick_id, drop_id = params.get("pickup"), params.get("dropoff")
    if not v.check(bool(pick_id and drop_id), f"pickup '{pick_id}', dropoff '{drop_id}'",
                   "delivery task without pickup/dropoff"):
        return v
    schema = parse_service_description(ctx.service_desc or "")
    places = schema.places

    # ------------------------------------------------------------ route
    arr_pick = _first_event(proof, "arrive", pick_id)
    arr_drop = _first_event(proof, "arrive", drop_id, after=arr_pick.t if arr_pick else float("inf"))
    v.check(arr_pick is not None, f"arrived at pick-up '{pick_id}'", "never arrived at the pick-up place")
    v.check(arr_drop is not None, f"arrived at drop-off '{drop_id}' after pick-up",
            "never arrived at the drop-off place after the pick-up")
    for label, pid, ev in (("pick-up", pick_id, arr_pick), ("drop-off", drop_id, arr_drop)):
        if ev is None:
            continue
        xy = (places.get(pid) or {}).get("xy")
        if not v.check(xy is not None, f"{label} place '{pid}' has coordinates",
                       f"{label} place has no coordinates on chain"):
            continue
        pose = nearest_pose(proof, ev.t)
        d = distance(pose, xy) if pose else None
        v.check(d is not None and d <= radius,
                f"pose at {label} arrival {'%.2f m' % d if d is not None else 'missing'} from "
                f"'{pid}' (max {radius:.2f} m)", f"robot was not at the {label} place")
    if not v.ok:
        return v

    # ------------------------------------------------------------ load
    dep_pick = _first_event(proof, "depart", pick_id, after=arr_pick.t)
    start = _stable(proof, t1=arr_pick.t)
    at_pick = _stable(proof, arr_pick.t, dep_pick.t if dep_pick else arr_drop.t)
    at_drop = _stable(proof, arr_drop.t)
    if not v.check(bool(start and at_pick and at_drop),
                   f"stable weight readings: start {len(start)}, pick-up {len(at_pick)}, drop-off {len(at_drop)}",
                   "missing weight readings"):
        return v
    empty = statistics.median(start)
    loaded = at_pick[-1] - empty
    arrived = at_drop[0] - empty
    after = at_drop[-1] - empty
    v.lines.append(f"  INFO  deck at start {empty:.3f} kg (reference for the other readings)")
    v.check(loaded >= min_pkg, f"package loaded at pick-up: {loaded:.3f} kg (min {min_pkg:.2f})",
            "no package was loaded at the pick-up place")
    v.check(abs(arrived - loaded) <= tol, f"still loaded at drop-off: {arrived:.3f} kg",
            "package weight changed in transit")
    v.check(abs(after) <= tol, f"deck empty after drop-off: {after:.3f} kg",
            "package was not unloaded at the drop-off place")
    declared = params.get("declared_weight_kg")
    if declared not in (None, ""):
        d_tol = max(tol, 0.1 * float(declared))
        v.check(abs(loaded - float(declared)) <= d_tol,
                f"matches declared weight {float(declared):.3f} kg (tol {d_tol:.3f})",
                "package weight differs from the declared weight")
    return v
