import json
import os

import pytest

from rodeo_common.description import encode_task_description, parse_task_description
from rodeo_common.proof import make_proof_uri, parse_proof_uri, sha256_path
from rodeo_common.service_description import (
    encode_service_description, parse_service_description, validate_task_params)
from rodeo_common.services_config import ConfigError, load_robot_config, parse_robot_config

HERE = os.path.dirname(os.path.abspath(__file__))
PANTHER = os.path.join(HERE, "..", "..", "..", "..", "config", "panther", "services.yaml")


def base_cfg(**over):
    d = {"robot": "panther", "wallet": "15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
         "services": [{"name": "Delivery", "category": "Logistics", "task_type": "ItemTransport",
                       "price_iec": 100,
                       "params": {"pickup": {"type": "place"}, "dropoff": {"type": "place"},
                                  "w": {"type": "number", "optional": True}}}],
         "places": {"a": {"label": "A", "xy": [1, 2]}, "b": {"label": "B"}}}
    d.update(over)
    return d


# ---------------------------------------------------------------- descriptions
def test_task_description_roundtrip():
    s = encode_task_description({"pickup": "a", "dropoff": "b"}, "fragile")
    d = parse_task_description(s)
    assert d.structured and d.version == 1
    assert d.params == {"pickup": "a", "dropoff": "b"} and d.note == "fragile"


@pytest.mark.parametrize("text", ["Package delivery", "", None, "[1, 2]", '{"no": "version"}',
                                  '{"v": 1, "params": "notadict"}'])
def test_free_text_and_malformed_parse_as_note(text):
    d = parse_task_description(text)
    assert not d.structured and d.params == {} and d.note == (text or "")


def test_encode_rejects_non_dict():
    with pytest.raises(TypeError):
        encode_task_description(["a"])


# ---------------------------------------------------------------- services.yaml
def test_panther_example_is_valid():
    cfg = load_robot_config(PANTHER)
    assert cfg.robot == "panther" and cfg.wallet.startswith("0x")
    svc = cfg.service_for("Logistics", "ItemTransport")
    assert svc is not None and svc.place_params == ["pickup", "dropoff"]
    assert cfg.places["samuel_desk"].waypoint == "P"
    assert cfg.service_for("Logistics", "Nope") is None
    assert all(p.xy is not None for p in cfg.places.values()), "every Panther place needs xy"


def test_wallet_gets_0x_prefix():
    assert parse_robot_config(base_cfg()).wallet == "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"


@pytest.mark.parametrize("over,msg", [
    ({"robot": "Panther-1"}, "namespace"),
    ({"wallet": "0x123"}, "Ethereum address"),
    ({"services": []}, "non-empty list"),
    ({"places": {}}, "no 'places'"),
    ({"places": {"a": {"label": "A", "xy": [1]}}}, "xy"),
    ({"places": {"Bad Id": {"label": "x"}}}, "place ids"),
])
def test_invalid_configs(over, msg):
    with pytest.raises(ConfigError, match=msg):
        parse_robot_config(base_cfg(**over))


def test_bad_price_and_param_type_and_duplicates():
    d = base_cfg(); d["services"][0]["price_iec"] = 0
    with pytest.raises(ConfigError, match="price_iec"):
        parse_robot_config(d)
    d = base_cfg(); d["services"][0]["params"]["x"] = {"type": "colour"}
    with pytest.raises(ConfigError, match="type"):
        parse_robot_config(d)
    d = base_cfg(); d["services"].append(dict(d["services"][0], name="Again"))
    with pytest.raises(ConfigError, match="offered twice"):
        parse_robot_config(d)


# ---------------------------------------------------------------- service description
def test_service_description_roundtrip_and_validation():
    cfg = parse_robot_config(base_cfg())
    text = encode_service_description(cfg, cfg.services[0])
    assert "waypoint" not in text
    sd = parse_service_description(text)
    assert sd.structured and sd.robot == "panther" and set(sd.places) == {"a", "b"}
    assert sd.places["a"]["xy"] == [1.0, 2.0] and sd.places["b"]["xy"] is None
    assert validate_task_params(sd, {"pickup": "a", "dropoff": "b"}) == []
    assert validate_task_params(sd, {"pickup": "a", "dropoff": "b", "w": 1.5}) == []
    errs = validate_task_params(sd, {"pickup": "zz", "w": "heavy", "extra": 1})
    assert any("unknown place 'zz'" in e for e in errs)
    assert any("missing parameter 'dropoff'" in e for e in errs)
    assert any("expected a number" in e for e in errs)
    assert any("unexpected parameter 'extra'" in e for e in errs)


def test_fixed_service_has_no_places_and_legacy_text():
    d = base_cfg(services=[{"name": "Tour", "category": "Guidance", "task_type": "LabTour",
                            "price_iec": 50}])
    cfg = parse_robot_config(d)
    desc = json.loads(encode_service_description(cfg, cfg.services[0]))
    assert desc["params"] == {} and "places" not in desc
    legacy = parse_service_description("Autonomous package delivery robot")
    assert not legacy.structured and legacy.summary == "Autonomous package delivery robot"


# ---------------------------------------------------------------- proofs
def test_proof_uri_and_hash(tmp_path):
    f = tmp_path / "p.mcap"; f.write_bytes(b"abc")
    uri = make_proof_uri(str(f))
    path, sha = parse_proof_uri(uri)
    assert path == str(f) and sha == sha256_path(str(f))
    assert sha == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    d = tmp_path / "bag"; d.mkdir(); (d / "x_0.mcap").write_bytes(b"1"); (d / "metadata.yaml").write_bytes(b"2")
    h1 = sha256_path(str(d)); (d / "x_0.mcap").write_bytes(b"changed")
    assert sha256_path(str(d)) != h1
    assert parse_proof_uri("file:///root/oracle/proofs/a.bag") == ("/root/oracle/proofs/a.bag", None)
    with pytest.raises(ValueError):
        parse_proof_uri("ipfs://Qm123")
