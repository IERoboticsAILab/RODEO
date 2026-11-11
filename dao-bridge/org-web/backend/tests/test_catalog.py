"""Catalog rules without a chain.  cd dao-bridge/org-web/backend && python -m pytest tests"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from catalog import build_catalog, task_description  # noqa: E402

DELIVERY = json.dumps({"v": 1, "robot": "panther", "summary": "Delivers a package",
                       "params": {"pickup": {"type": "place", "label": "Pick-up place", "optional": False, "default": "a"},
                                  "dropoff": {"type": "place", "label": "Deliver to", "optional": False},
                                  "w": {"type": "number", "label": "kg", "optional": True}},
                       "places": {"a": {"label": "A", "xy": [0, 0]}, "b": {"label": "B", "xy": [1, 1]}},
                       "settings": {}})


def svc(id, price=100, active=True, busy=False, cat="Logistics", typ="ItemTransport", desc=DELIVERY, name="Delivery"):
    return {"id": id, "name": name, "description": desc, "serviceCategory": cat, "serviceType": typ,
            "priceWei": str(price * 10**18), "active": active, "busy": busy}


def test_catalog_groups_and_hides_offline():
    rows = [svc(1, 100), svc(2, 80, busy=True), svc(3, 50, active=False),
            svc(4, 20, cat="Energy", typ="Charging", desc="Wireless charging", name="Charging")]
    cat = build_catalog(rows)
    assert [e["key"] for e in cat] == ["Energy/Charging", "Logistics/ItemTransport"]
    d = cat[1]
    assert d["providers"] == 2 and d["free"] == 1          # inactive service 3 not counted
    assert d["minPriceIec"] == 80 and d["pickPriceIec"] == 100   # cheapest is busy: free one is picked
    assert d["structured"] and set(d["places"]) == {"a", "b"} and d["places"]["a"] == {"label": "A"}
    assert d["params"]["pickup"]["default"] == "a"
    assert not cat[0]["structured"] and cat[0]["summary"] == "Wireless charging" and cat[0]["params"] == {}


def test_busy_only_kind_still_listed():
    d = build_catalog([svc(1, busy=True)])[0]
    assert d["free"] == 0 and d["providers"] == 1


def test_task_description():
    rows = [svc(1)]
    out = json.loads(task_description(rows, "Logistics", "ItemTransport", {"dropoff": "b"}, "fragile"))
    assert out == {"v": 1, "params": {"dropoff": "b"}, "note": "fragile"}
    assert task_description(rows, "Logistics", "ItemTransport", None, "free text") == "free text"
    with pytest.raises(ValueError, match="unknown place 'zz'"):
        task_description(rows, "Logistics", "ItemTransport", {"dropoff": "zz"}, "")
    with pytest.raises(ValueError, match="missing parameter 'dropoff'"):
        task_description(rows, "Logistics", "ItemTransport", {}, "")
    with pytest.raises(ValueError, match="no active service"):
        task_description(rows, "Security", "Patrol", {}, "")
    legacy = [svc(2, desc="free text service")]
    assert json.loads(task_description(legacy, "Logistics", "ItemTransport", {}, "n")) == {"v": 1, "params": {}, "note": "n"}
    with pytest.raises(ValueError, match="takes no parameters"):
        task_description(legacy, "Logistics", "ItemTransport", {"x": 1}, "")


def test_robot_only_services_hidden():
    station = json.dumps({"v": 1, "robot": "station", "summary": "", "params": {}, "settings": {"robot_only": True}})
    cat = build_catalog([svc(1), svc(2, 20, cat="Energy", typ="Charging", desc=station, name="Charging")])
    assert [e["key"] for e in cat] == ["Logistics/ItemTransport"]
