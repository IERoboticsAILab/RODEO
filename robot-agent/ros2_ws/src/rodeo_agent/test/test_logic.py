import os
from types import SimpleNamespace as NS

from rodeo_common.description import encode_task_description
from rodeo_common.service_description import encode_service_description
from rodeo_common.services_config import load_robot_config

from rodeo_agent.logic import (
    WEI, OnChainService, plan_service_sync, prepare_task, tasks_to_recover)

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = load_robot_config(os.path.join(HERE, "..", "..", "..", "..", "config", "panther", "services.yaml"))
SPEC = CFG.services[0]
DESC = encode_service_description(CFG, SPEC)
WALLET = CFG.wallet


def svc(id, name="Delivery", desc=DESC, cat="Logistics", typ="ItemTransport", price=100, active=True, busy=False):
    return OnChainService(id, name, desc, cat, typ, price * WEI, active, busy)


def task(id=1, desc="Package delivery", cat="Logistics", typ="ItemTransport", executor=WALLET,
         status=1, active=True, proof="none"):
    return NS(id=id, description=desc, category=cat, task_type=typ, executor=executor,
              status=status, active=active, proof_uri=proof)


# ------------------------------------------------------------------ service sync
def test_fresh_wallet_registers():
    p = plan_service_sync(CFG, [])
    assert [s.name for s, _ in p.register] == ["Delivery"] and not p.deactivate and not p.keep


def test_exact_active_service_is_reused():
    p = plan_service_sync(CFG, [svc(3)])
    assert p.keep == {("Logistics", "ItemTransport"): 3}
    assert not p.register and not p.activate and not p.deactivate


def test_exact_inactive_service_is_reactivated():
    p = plan_service_sync(CFG, [svc(3, active=False)])
    assert p.activate == [3] and p.keep[("Logistics", "ItemTransport")] == 3


def test_emulator_duplicates_replaced():
    # what the demo chain looks like today: two "Delivery Service" entries with free-text descriptions
    old = [svc(1, "Delivery Service", "Autonomous package delivery robot"),
           svc(2, "Delivery Service", "Autonomous package delivery robot")]
    p = plan_service_sync(CFG, old)
    assert len(p.register) == 1 and sorted(i for i, _ in p.deactivate) == [1, 2]


def test_price_change_registers_new_and_busy_old_warns():
    p = plan_service_sync(CFG, [svc(4, price=80, busy=True)])
    assert len(p.register) == 1 and not p.deactivate and p.warnings


def test_unknown_kind_deactivated_unless_disabled():
    other = svc(5, "Patrol", "x", cat="Security", typ="Patrol")
    assert (5, "Security/Patrol not in services.yaml") in plan_service_sync(CFG, [svc(3), other]).deactivate
    assert plan_service_sync(CFG, [svc(3), other], deactivate_unknown=False).deactivate == []


# ------------------------------------------------------------------ task preparation
def test_free_text_task_uses_defaults():
    prep, why = prepare_task(CFG, task())
    assert why is None and prep.note == "Package delivery"
    assert prep.params["pickup"] == "package_pickup" and prep.params["dropoff"] == "package_dropoff"


def test_structured_task():
    d = encode_task_description({"pickup": "farah_desk", "dropoff": "samuel_desk",
                                 "recipient": "Samuel"}, "fragile")
    prep, why = prepare_task(CFG, task(desc=d))
    assert why is None and prep.params["dropoff"] == "samuel_desk" and prep.note == "fragile"


def test_bad_tasks_rejected_with_reason():
    _, why = prepare_task(CFG, task(cat="Security", typ="Patrol"))
    assert "offers no Security/Patrol" in why
    _, why = prepare_task(CFG, task(desc=encode_task_description({"dropoff": "mars"})))
    assert "unknown place 'mars'" in why


# ------------------------------------------------------------------ recovery
def test_recovery():
    ts = [task(1), task(2, proof="file:///p#sha256=ab"), task(3, executor="0x" + "1" * 40),
          task(4, status=2), task(5, active=False), task(6, executor=WALLET.lower())]
    assert tasks_to_recover(ts, WALLET) == ([1, 6], [2])
