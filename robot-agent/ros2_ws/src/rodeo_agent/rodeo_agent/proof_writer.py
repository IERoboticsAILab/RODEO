"""
ProofWriter - writes a RODEO proof bag (ROS 2 bag, MCAP storage).

Used by executors. MCAP stores the message definitions inside the file, so the
oracle can decode rodeo_interfaces messages without having them built.

    with ProofWriter(goal.proof_dir, goal) as proof:
        proof.pose(x, y, yaw)
        proof.event(TaskEvent.ARRIVE, place="package_pickup")
        proof.weight(1.2, stable=True)
    result.proof_path = proof.path          # a bag directory

Timestamps are wall-clock (the oracle compares them with the chain's block
times), so all machines should run NTP.
"""
from __future__ import annotations

import math
import os
import time

import rosbag2_py
from builtin_interfaces.msg import Time
from geometry_msgs.msg import PoseStamped
from rclpy.serialization import serialize_message

from rodeo_common.proof import (
    TOPIC_EVENTS, TOPIC_MANIFEST, TOPIC_PAYLOAD_WEIGHT, TOPIC_POSE, proof_basename)
from rodeo_interfaces.msg import PayloadWeight, ProofManifest, TaskEvent

_TYPES = {
    TOPIC_MANIFEST: "rodeo_interfaces/msg/ProofManifest",
    TOPIC_POSE: "geometry_msgs/msg/PoseStamped",
    TOPIC_EVENTS: "rodeo_interfaces/msg/TaskEvent",
    TOPIC_PAYLOAD_WEIGHT: "rodeo_interfaces/msg/PayloadWeight",
}


def _stamp(t_ns: int) -> Time:
    return Time(sec=t_ns // 1_000_000_000, nanosec=t_ns % 1_000_000_000)


class ProofWriter:
    def __init__(self, proof_dir: str, goal, storage_id: str = "mcap"):
        """``goal`` is the rodeo_interfaces ExecuteTask goal being executed."""
        os.makedirs(proof_dir, exist_ok=True)
        t0 = time.time_ns()
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime(t0 / 1e9))
        self.path = os.path.join(proof_dir, proof_basename(goal.task_id, goal.robot or "robot", stamp))
        self._writer = rosbag2_py.SequentialWriter()
        self._writer.open(rosbag2_py.StorageOptions(uri=self.path, storage_id=storage_id),
                          rosbag2_py.ConverterOptions("cdr", "cdr"))
        self._topics = set()
        self._write(TOPIC_MANIFEST, ProofManifest(
            format_version=ProofManifest.FORMAT_VERSION, task_id=int(goal.task_id),
            executor=goal.executor, robot=goal.robot, category=goal.category,
            task_type=goal.task_type, params_json=goal.params_json, start=_stamp(t0)), t0)

    # ------------------------------------------------------------------ records
    def pose(self, x: float, y: float, yaw: float = 0.0, frame: str = "map"):
        t = time.time_ns()
        m = PoseStamped()
        m.header.stamp, m.header.frame_id = _stamp(t), frame
        m.pose.position.x, m.pose.position.y = float(x), float(y)
        m.pose.orientation.z, m.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        self._write(TOPIC_POSE, m, t)

    def event(self, type_: str, place: str = "", text: str = "", actor: str = ""):
        t = time.time_ns()
        self._write(TOPIC_EVENTS, TaskEvent(stamp=_stamp(t), type=type_, place=place,
                                            text=text, actor=actor), t)

    def weight(self, kg: float, stable: bool = True):
        t = time.time_ns()
        self._write(TOPIC_PAYLOAD_WEIGHT, PayloadWeight(stamp=_stamp(t), kg=float(kg),
                                                        stable=bool(stable)), t)

    # ------------------------------------------------------------------ plumbing
    def _write(self, topic: str, msg, t_ns: int):
        if topic not in self._topics:
            self._writer.create_topic(rosbag2_py.TopicMetadata(
                name=topic, type=_TYPES[topic], serialization_format="cdr"))
            self._topics.add(topic)
        self._writer.write(topic, serialize_message(msg), t_ns)

    def close(self) -> str:
        """Flush and close the bag (rosbag2_py closes on destruction); returns its path."""
        if self._writer is not None:
            self._writer = None
            import gc
            gc.collect()
        return self.path

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
