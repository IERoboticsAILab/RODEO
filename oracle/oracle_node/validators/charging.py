"""
Charging validator (Energy / Charging).

The proof is written by the charging station (the institution's executor), from
the station's own measurements, and checked against the task:

    session   a "session start" and a "session end" event, in that order, both
              naming the robot that posted (and paid for) the task as actor
    energy    delivered energy, integrated from the station's voltage and current
              samples within the session, is at least the service's min_wh
              (from its on-chain description settings; default CHARGING_MIN_WH)
    charging  at least one sample shows active charging (ramp_up, cc or cv)

A real station's samples come from the WiBotic transmitter's telemetry; the
stub in rodeo_agent/station_executor.py simulates them.
"""
from __future__ import annotations

import os

from rodeo_common.service_description import parse_service_description

from . import Verdict, register

SESSION_START, SESSION_END = "session start", "session end"
CHARGING_STATES = ("ramp_up", "cc", "cv")


def delivered_wh(samples) -> float:
    """Trapezoidal integral of V*I over [(t, V, I, state)], in Wh."""
    wh = 0.0
    for (t0, v0, i0, _), (t1, v1, i1, _) in zip(samples, samples[1:]):
        if t1 > t0:
            wh += (v0 * i0 + v1 * i1) / 2.0 * (t1 - t0) / 3600.0
    return wh


def _event(proof, text):
    for e in proof.events:
        if e.type == "note" and e.text == text:
            return e
    return None


@register("Energy", "Charging")
def validate(ctx) -> Verdict:
    proof, task, v = ctx.proof, ctx.task, Verdict(ok=True)
    settings = parse_service_description(ctx.service_desc or "").settings
    min_wh = float(settings.get("min_wh", os.environ.get("CHARGING_MIN_WH", "0.1")))

    start, end = _event(proof, SESSION_START), _event(proof, SESSION_END)
    if not v.check(start is not None and end is not None and end.t >= start.t,
                   "session start and end recorded", "no complete charging session in the proof"):
        return v
    payer = (task.creator or "").lower()
    v.check(start.actor.lower() == payer and end.actor.lower() == payer,
            f"session for the paying robot {task.creator}",
            "charged robot is not the one that paid")

    samples = [s for s in proof.charge if start.t <= s[0] <= end.t]
    if not v.check(len(samples) >= 2, f"{len(samples)} charge samples in the session",
                   "no charge measurements in the session"):
        return v
    wh = delivered_wh(samples)
    v.check(wh >= min_wh, f"delivered {wh:.3f} Wh in {end.t - start.t:.0f} s (min {min_wh:g} Wh)",
            f"too little energy delivered ({wh:.3f} Wh, min {min_wh:g})")
    states = sorted({s[3] for s in samples})
    v.check(any(s in CHARGING_STATES for s in states), f"charge states seen: {', '.join(states)}",
            "station never reported active charging")
    return v
