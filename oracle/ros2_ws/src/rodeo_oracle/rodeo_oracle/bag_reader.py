"""
Read a RODEO proof with rosbag2 (native ROS 2) into the same RodeoProof
structure the pure-Python oracle uses, so the shared checks and validator rules
are reused unchanged.
"""
from __future__ import annotations

import os

import rosbag2_py
import yaml
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

from oracle_node.proofs import Event, RodeoProof, stamp_s
from rodeo_common.proof import TOPIC_EVENTS, TOPIC_MANIFEST, TOPIC_PAYLOAD_WEIGHT, TOPIC_POSE


def storage_id(path: str) -> str:
    with open(os.path.join(path, "metadata.yaml")) as f:
        info = yaml.safe_load(f)["rosbag2_bagfile_information"]
    return info.get("storage_identifier", "mcap")


def read_proof(path: str) -> RodeoProof:
    """``path`` is a rosbag2 bag directory (what ProofWriter produces)."""
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=path, storage_id=storage_id(path)),
                rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    classes = {}
    proof = RodeoProof()
    while reader.has_next():
        topic, data, t_ns = reader.read_next()
        proof.log_times.append(t_ns * 1e-9)
        proof.topics[topic] = proof.topics.get(topic, 0) + 1
        if topic not in (TOPIC_MANIFEST, TOPIC_POSE, TOPIC_EVENTS, TOPIC_PAYLOAD_WEIGHT):
            continue
        if topic not in classes:
            classes[topic] = get_message(types[topic])
        m = deserialize_message(data, classes[topic])
        if topic == TOPIC_MANIFEST:
            proof.manifests.append(m)
        elif topic == TOPIC_POSE:
            proof.poses.append((stamp_s(m.header.stamp), m.pose.position.x, m.pose.position.y))
        elif topic == TOPIC_EVENTS:
            proof.events.append(Event(stamp_s(m.stamp), m.type, m.place, m.text, m.actor))
        else:
            proof.weights.append((stamp_s(m.stamp), float(m.kg), bool(m.stable)))
    del reader
    proof.poses.sort()
    proof.events.sort(key=lambda e: e.t)
    proof.weights.sort()
    return proof
