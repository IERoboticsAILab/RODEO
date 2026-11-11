"""The ROS 2 reader (rosbag2) and the pure-Python reader (rosbags) must see the same proof.
Needs a sourced ROS 2 workspace with rodeo_interfaces and rodeo_agent built."""
import json
from types import SimpleNamespace as NS

import pytest

rosbag2_py = pytest.importorskip("rosbag2_py")

from oracle_node.proofs import read_rodeo_proof  # noqa: E402
from rodeo_agent.proof_writer import ProofWriter  # noqa: E402
from rodeo_interfaces.msg import TaskEvent  # noqa: E402

from rodeo_oracle.bag_reader import read_proof  # noqa: E402


def test_readers_agree(tmp_path):
    goal = NS(task_id=5, executor="0x" + "ab" * 20, robot="panther", category="Logistics",
              task_type="ItemTransport", params_json=json.dumps({"pickup": "a", "dropoff": "b"}))
    with ProofWriter(str(tmp_path), goal) as w:
        w.weight(0.0); w.pose(1.0, 2.0, 0.5); w.event(TaskEvent.ARRIVE, place="a")
        w.weight(1.25); w.event(TaskEvent.CONFIRM, place="b", actor="Samuel")
    a, b = read_proof(w.path), read_rodeo_proof(w.path)
    assert a.manifest.task_id == b.manifest.task_id == 5
    assert a.params == b.params == {"pickup": "a", "dropoff": "b"}
    assert a.poses == b.poses and a.weights == b.weights
    assert [(e.type, e.place, e.actor) for e in a.events] == [(e.type, e.place, e.actor) for e in b.events]
    assert a.log_times == b.log_times and a.topics == b.topics
