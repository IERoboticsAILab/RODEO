"""Oracle checks without a chain: synthetic proofs and the committed sample bags.

    cd oracle && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
        PYTHONPATH=.:../robot-agent/ros2_ws/src/rodeo_common python -m pytest tests

(web3 6 ships a pytest plugin that fails to import with newer eth-typing;
disabling plugin autoload avoids it.)
"""
import json
import os
from types import SimpleNamespace as NS

import pytest

from rodeo_common.service_description import encode_service_description
from rodeo_common.services_config import load_robot_config

from oracle_node.checks import check_rodeo_proof
from oracle_node.proofs import Event, RodeoProof
from oracle_node.validators import validator_for
from oracle_node.validators.waste_ros1 import validate_bag

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = load_robot_config(os.path.join(HERE, "..", "..", "robot-agent", "config", "panther", "services.yaml"))
DESC = encode_service_description(CFG, CFG.services[0])
WALLET = CFG.wallet
PICK, DROP = CFG.places["package_pickup"].xy, CFG.places["package_dropoff"].xy
PARAMS = {"dropoff": "package_dropoff", "pickup": "package_pickup", "recipient": "the recipient", "sender": "RODEO"}
T0 = 1_000_000.0


def task(**kw):
    d = dict(id=7, description="Package delivery", category="Logistics", task_type="ItemTransport",
             executor=WALLET)
    d.update(kw)
    return NS(**d)


def proof(params=PARAMS, task_id=7, drop_xy=DROP, unload=True, confirm_by="the recipient", load_kg=1.2):
    p = RodeoProof()
    p.manifests.append(NS(format_version=1, task_id=task_id, executor=WALLET, robot="panther",
                          category="Logistics", task_type="ItemTransport", params_json=json.dumps(params)))
    seq = [  # (t, kind, data)
        (1, "w", 0.0), (2, "pose", PICK), (2, "ev", ("arrive", "package_pickup", "")),
        (3, "w", 0.0), (4, "w", load_kg), (5, "ev", ("depart", "package_pickup", "")),
        (9, "pose", drop_xy), (9, "ev", ("arrive", params.get("dropoff", ""), "")),
        (10, "w", load_kg), (11, "w", 0.0 if unload else load_kg)]
    if confirm_by:
        seq.append((12, "ev", ("confirm", params.get("dropoff", ""), confirm_by)))
    for dt, kind, data in seq:
        t = T0 + dt
        p.log_times.append(t)
        if kind == "w":
            p.weights.append((t, data, True))
        elif kind == "pose":
            p.poses.append((t, data[0], data[1]))
        else:
            p.events.append(Event(t, data[0], data[1], "", data[2]))
    return p


def run(t, p, window=(T0, T0 + 20)):
    v = check_rodeo_proof(t, p, window, DESC, sha_ok=True, reused_by=None, tolerance_s=5)
    if v.ok:
        sub = validator_for(t.category, t.task_type)(NS(task=t, proof=p, service_desc=DESC, settings=None))
        v.lines += sub.lines
        v.ok, v.reason = sub.ok, sub.reason
    return v


def test_good_delivery_passes():
    v = run(task(), proof())
    assert v.ok, v.lines


@pytest.mark.parametrize("t_kw,p_kw,reason", [
    ({}, {"task_id": 8}, "proof is for task 8, not 7"),
    ({"executor": "0x" + "1" * 40}, {}, "proof executor is not the task's executor"),
    ({}, {"params": dict(PARAMS, dropoff="samuel_desk")}, "proof parameters do not match the task"),
    ({}, {"drop_xy": (DROP[0] + 5, DROP[1])}, "robot was not at the drop-off place"),
    ({}, {"unload": False}, "package was not unloaded at the drop-off place"),
    ({}, {"confirm_by": None}, "receipt not confirmed at the drop-off place"),
    ({}, {"confirm_by": "someone else"}, "receipt confirmed by someone else"),
    ({}, {"load_kg": 0.0}, "no package was loaded at the pick-up place"),
])
def test_bad_deliveries_rejected(t_kw, p_kw, reason):
    v = run(task(**t_kw), proof(**p_kw))
    assert not v.ok and v.reason == reason, v.lines


def test_time_window_and_hash_and_reuse():
    t, p = task(), proof()
    assert run(t, p, window=(T0 + 10, T0 + 20)).reason == "proof recorded outside the task's time window"   # starts 9 s early
    assert run(t, p, window=(T0, T0 + 5)).reason == "proof recorded outside the task's time window"         # ends 7 s late
    assert run(t, p, window=(T0 + 4, T0 + 8)).ok                                                               # within 5 s
    v = check_rodeo_proof(t, p, (T0, T0 + 20), DESC, sha_ok=False, reused_by=None, tolerance_s=5)
    assert v.reason == "proof changed after submission (hash mismatch)"
    v = check_rodeo_proof(t, p, (T0, T0 + 20), DESC, sha_ok=True, reused_by=3, tolerance_s=5)
    assert v.reason == "proof reused from another task"


def test_declared_weight():
    d = json.dumps({"v": 1, "params": {"declared_weight_kg": 2.0}, "note": ""})
    params = dict(PARAMS, declared_weight_kg=2.0)
    assert not run(task(description=d), proof(params=params)).ok          # carried 1.2 kg, declared 2.0
    assert run(task(description=d), proof(params=params, load_kg=2.0)).ok


def test_legacy_waste_bags():
    good = validate_bag(os.path.join(HERE, "..", "proofs", "task_tid10_20250910_145742.bag"))
    assert good.ok and any("total 10.956 m" in l for l in good.lines)
    bad = validate_bag(os.path.join(HERE, "..", "proofs", "task_tid1_20250904_164349.bag"))
    assert not bad.ok and bad.reason == "Disposal event missing or incorrect"
