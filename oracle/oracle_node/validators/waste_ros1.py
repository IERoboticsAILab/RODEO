"""
Waste-sorting validator for legacy ROS 1 proofs (.bag), ported from the original
oracle's ros1_validator.py.

The original replayed the bag with `rosbag play` into a ROS 1 node; this reads
the same messages directly with `rosbags`, in timestamp order, and applies the
same rules, so no ROS install or ROS master is needed. Checks:

    base path   total path length on /odom_mocap >= MIN_PATH_METERS
    arm         net joint change on /vx300s/joint_states >= ARM_TOTAL_DELTA_TOL,
                with at least one arm movement
    disposal    a /disposal_event message with "correct": true

These proofs carry no manifest, so nothing ties them to a task: the original
demo bag passes for any task. They are accepted for the original demo only.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

from rosbags.highlevel import AnyReader

from . import Verdict


def _env(name, default):
    return float(os.environ.get(name, default))


def _segments(samples, eps, min_sec):
    """[(t, moving)] -> state segments [{state, t0, t1}] of at least min_sec (as the original)."""
    segs, cur, t0, last_t = [], None, None, None
    for t, moving in samples:
        want = "moving" if moving else "stopped"
        if cur is None:
            cur, t0 = want, t
        elif want != cur:
            if t > t0:
                segs.append({"state": cur, "t0": t0, "t1": t})
            cur, t0 = want, t
        last_t = t
    if cur is not None and last_t is not None and last_t > t0:
        segs.append({"state": cur, "t0": t0, "t1": last_t})
    return [s for s in segs if s["t1"] - s["t0"] >= min_sec]


def validate_bag(path: str) -> Verdict:
    pos_eps = _env("POS_EPS", "0.002")
    arm_eps = _env("ARM_POS_EPS", "0.005")
    arm_tol = _env("ARM_TOTAL_DELTA_TOL", "0.05")
    min_arm_sec = _env("MIN_ARM_STATE_SEC", "0.0")
    min_path = _env("MIN_PATH_METERS", "0.10")
    joint_topic = os.environ.get("JOINT_TOPIC", "/vx300s/joint_states")

    path_len, last_pos, last_t = 0.0, None, None
    arm_samples, arm_init, arm_last, arm_last_t = [], None, None, None
    arm_net, joint_net, arm_episodes = 0.0, {}, 0
    disposal_ok = False

    def stamp(msg, t_ns):
        try:
            t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            return t if t > 0 else t_ns * 1e-9
        except AttributeError:
            return t_ns * 1e-9

    with AnyReader([Path(path)]) as r:
        conns = [c for c in r.connections if c.topic in ("/odom_mocap", joint_topic, "/disposal_event")]
        for c, t_ns, raw in r.messages(connections=conns):
            m = r.deserialize(raw, c.msgtype)
            if c.topic == "/odom_mocap":
                x, y, t = m.pose.pose.position.x, m.pose.pose.position.y, stamp(m, t_ns)
                if last_pos is not None and t >= last_t:
                    path_len += math.hypot(x - last_pos[0], y - last_pos[1])
                last_pos, last_t = (x, y), t
            elif c.topic == joint_topic:
                cur, t = dict(zip(m.name, m.position)), stamp(m, t_ns)
                if arm_init is None:
                    arm_init = dict(cur)
                    joint_net = {j: 0.0 for j in cur}
                if arm_last is not None and t >= arm_last_t:
                    step = 0.0
                    for j, p in cur.items():
                        if j in arm_last:
                            step = max(step, abs(p - arm_last[j]))
                            joint_net[j] = max(joint_net.get(j, 0.0), abs(p - arm_init.get(j, p)))
                    arm_samples.append((t, step > arm_eps))
                elif arm_last is None:
                    arm_samples.append((t, False))
                arm_last, arm_last_t = cur, t
                arm_net = max(arm_net, sum(abs(cur[j] - p0) for j, p0 in arm_init.items() if j in cur))
            else:
                try:
                    if bool(json.loads(m.data).get("correct", False)):
                        disposal_ok = True
                except (ValueError, AttributeError):
                    pass

    # movement episodes, counted as in the original (transitions into "moving")
    prev = None
    for _, moving in arm_samples:
        if moving and prev is not True:
            arm_episodes += 1
        prev = moving
    arm_moves = max(arm_episodes, sum(1 for s in _segments(arm_samples, arm_eps, min_arm_sec)
                                      if s["state"] == "moving"))

    v = Verdict(ok=True)
    v.lines.append("  INFO  legacy ROS 1 proof: not bound to a task (no manifest)")
    v.check(path_len >= min_path, f"Base path: total {path_len:.3f} m, min {min_path:.3f} m",
            f"Base path too short, {path_len:.3f} m, min {min_path:.3f} m")
    v.check(arm_net >= arm_tol and arm_moves >= 1,
            f"Arm: net delta {arm_net:.4f} rad, tol {arm_tol:.4f} rad, moves {arm_moves}",
            f"Arm did not move enough, net {arm_net:.4f} rad")
    if joint_net:
        top = sorted(joint_net.items(), key=lambda kv: kv[1], reverse=True)[:3]
        v.lines.append("  INFO  Arm top joints by change: " + ", ".join(f"{j}:{d:.3f}" for j, d in top))
    v.check(disposal_ok, "Disposal event: correct flag " + ("seen True" if disposal_ok else "never True"),
            "Disposal event missing or incorrect")
    return v
