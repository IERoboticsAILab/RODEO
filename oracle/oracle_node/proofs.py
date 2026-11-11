"""
Reading proofs.

A RODEO proof is a ROS 2 bag (normally a bag directory with MCAP storage)
holding /rodeo/manifest, /rodeo/pose, /rodeo/events and service-specific
topics. It is read with the `rosbags` library: pure Python, no ROS install, and
MCAP carries the message definitions, so custom rodeo_interfaces messages
decode without being built here. Legacy proofs (ROS 1 .bag, energy .csv) are
recognised so their validators can be chosen.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path

from rosbags.highlevel import AnyReader
from rosbags.typesys import Stores, get_typestore

from rodeo_common.proof import (
    TOPIC_CHARGE, TOPIC_EVENTS, TOPIC_MANIFEST, TOPIC_PAYLOAD_WEIGHT, TOPIC_POSE)

PROOF_TOPICS = (TOPIC_MANIFEST, TOPIC_POSE, TOPIC_EVENTS, TOPIC_PAYLOAD_WEIGHT, TOPIC_CHARGE)

KIND_RODEO, KIND_ROS1_BAG, KIND_CSV, KIND_UNKNOWN = "rodeo", "ros1-bag", "csv", "unknown"


def stamp_s(t) -> float:
    return t.sec + t.nanosec * 1e-9


@dataclass
class Event:
    t: float
    type: str
    place: str
    text: str
    actor: str


@dataclass
class RodeoProof:
    manifests: list = field(default_factory=list)   # raw manifest messages
    poses: list = field(default_factory=list)       # (t, x, y)
    events: list = field(default_factory=list)      # [Event]
    weights: list = field(default_factory=list)     # (t, kg, stable)
    charge: list = field(default_factory=list)      # (t, voltage_v, current_a, state)
    log_times: list = field(default_factory=list)   # every message's log time (s)
    topics: dict = field(default_factory=dict)      # topic -> message count

    @property
    def manifest(self):
        return self.manifests[0] if len(self.manifests) == 1 else None

    @property
    def params(self) -> dict:
        try:
            return json.loads(self.manifest.params_json or "{}")
        except (AttributeError, ValueError):
            return {}


def detect_kind(path: str) -> str:
    p = Path(path)
    if p.is_dir() and (p / "metadata.yaml").exists():
        return KIND_RODEO
    if p.suffix in (".mcap", ".db3"):
        return KIND_RODEO
    if p.suffix == ".bag":
        return KIND_ROS1_BAG
    if p.suffix == ".csv":
        return KIND_CSV
    return KIND_UNKNOWN


def read_rodeo_proof(path: str) -> RodeoProof:
    proof = RodeoProof()
    with AnyReader([Path(path)], default_typestore=get_typestore(Stores.ROS2_HUMBLE)) as r:
        for c in r.connections:
            proof.topics[c.topic] = proof.topics.get(c.topic, 0) + c.msgcount
        wanted = [c for c in r.connections if c.topic in PROOF_TOPICS]
        for c, t_ns, raw in r.messages():
            proof.log_times.append(t_ns * 1e-9)
            if c not in wanted:
                continue
            m = r.deserialize(raw, c.msgtype)
            if c.topic == TOPIC_MANIFEST:
                proof.manifests.append(m)
            elif c.topic == TOPIC_POSE:
                proof.poses.append((stamp_s(m.header.stamp), m.pose.position.x, m.pose.position.y))
            elif c.topic == TOPIC_EVENTS:
                proof.events.append(Event(stamp_s(m.stamp), m.type, m.place, m.text, m.actor))
            elif c.topic == TOPIC_PAYLOAD_WEIGHT:
                proof.weights.append((stamp_s(m.stamp), float(m.kg), bool(m.stable)))
            elif c.topic == TOPIC_CHARGE:
                proof.charge.append((stamp_s(m.stamp), float(m.voltage_v), float(m.current_a), m.state))
    proof.charge.sort()
    proof.poses.sort()
    proof.events.sort(key=lambda e: e.t)
    proof.weights.sort()
    return proof


def nearest_pose(proof: RodeoProof, t: float, window_s: float = 2.0):
    """The pose closest in time to t (within window_s), or None."""
    best = None
    for pt, x, y in proof.poses:
        dt = abs(pt - t)
        if dt <= window_s and (best is None or dt < best[0]):
            best = (dt, x, y)
    return None if best is None else (best[1], best[2])


def distance(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def path_size(path: str) -> int:
    if os.path.isdir(path):
        return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs)
    return os.path.getsize(path)
