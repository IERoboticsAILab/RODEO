"""
services.yaml - what one robot offers to RODEO.

    robot: panther                       # namespace: /panther/dao/..., /panther/rodeo/...
    wallet: "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
    services:
      - name: Delivery
        category: Logistics
        task_type: ItemTransport
        price_iec: 100
        summary: Picks up a package and delivers it to a desk
        params:                          # optional; omit for fixed services
          pickup:  {type: place, label: Pick-up place}
          dropoff: {type: place, label: Deliver to}
          declared_weight_kg: {type: number, label: Package weight (kg), optional: true}
        settings: {wait_s: 60}           # free-form, for the executor
    places:                              # shared by all services of this robot
      samuel_desk: {label: "Samuel's desk", waypoint: P, xy: [1.2, 3.4]}
    charging:
      max_price_iec: 20

``waypoint`` is the executor's own name for the place; ``xy`` (map frame, m) is
what the oracle checks poses against and may be left null until measured.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import yaml

PARAM_TYPES = ("place", "text", "number")
_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")
_ADDR = re.compile(r"^(0x)?[0-9a-fA-F]{40}$")


class ConfigError(ValueError):
    pass


@dataclass
class ParamSpec:
    name: str
    type: str
    label: str
    optional: bool = False


@dataclass
class Place:
    id: str
    label: str
    waypoint: str = ""
    xy: list | None = None           # [x, y] or [x, y, yaw]; None if not measured yet


@dataclass
class ServiceSpec:
    name: str
    category: str
    task_type: str
    price_iec: int
    summary: str = ""
    params: dict = field(default_factory=dict)      # name -> ParamSpec
    settings: dict = field(default_factory=dict)

    @property
    def place_params(self) -> list:
        return [p.name for p in self.params.values() if p.type == "place"]


@dataclass
class RobotConfig:
    robot: str
    wallet: str
    services: list = field(default_factory=list)    # [ServiceSpec]
    places: dict = field(default_factory=dict)      # id -> Place
    charging: dict = field(default_factory=dict)

    def service_for(self, category: str, task_type: str):
        for s in self.services:
            if s.category == category and s.task_type == task_type:
                return s
        return None


def _req_str(d: dict, key: str, where: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ConfigError(f"{where}: '{key}' must be a non-empty string")
    return v.strip()


def _parse_xy(v, where: str):
    if v is None:
        return None
    if (not isinstance(v, (list, tuple)) or len(v) not in (2, 3)
            or not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in v)):
        raise ConfigError(f"{where}: 'xy' must be null, [x, y] or [x, y, yaw]")
    return [float(c) for c in v]


def parse_robot_config(d: dict) -> RobotConfig:
    if not isinstance(d, dict):
        raise ConfigError("services.yaml must contain a mapping")
    robot = _req_str(d, "robot", "services.yaml")
    if not _IDENT.match(robot):
        raise ConfigError(f"robot '{robot}': use lowercase letters, digits and _ (it becomes the ROS namespace)")
    wallet = _req_str(d, "wallet", "services.yaml")
    if not _ADDR.match(wallet):
        raise ConfigError(f"wallet '{wallet}' is not an Ethereum address")
    if not wallet.startswith("0x"):
        wallet = "0x" + wallet

    places = {}
    for pid, p in (d.get("places") or {}).items():
        where = f"places.{pid}"
        if not isinstance(pid, str) or not _IDENT.match(pid):
            raise ConfigError(f"{where}: place ids use lowercase letters, digits and _")
        if not isinstance(p, dict):
            raise ConfigError(f"{where}: must be a mapping")
        places[pid] = Place(id=pid, label=_req_str(p, "label", where),
                            waypoint=str(p.get("waypoint") or ""),
                            xy=_parse_xy(p.get("xy"), where))

    services, seen = [], set()
    raw_services = d.get("services")
    if not isinstance(raw_services, list) or not raw_services:
        raise ConfigError("services.yaml: 'services' must be a non-empty list")
    for i, s in enumerate(raw_services):
        where = f"services[{i}]"
        if not isinstance(s, dict):
            raise ConfigError(f"{where}: must be a mapping")
        name = _req_str(s, "name", where)
        where = f"service '{name}'"
        category, task_type = _req_str(s, "category", where), _req_str(s, "task_type", where)
        if (category, task_type) in seen:
            raise ConfigError(f"{where}: {category}/{task_type} is offered twice by this robot")
        seen.add((category, task_type))
        price = s.get("price_iec")
        if not isinstance(price, int) or isinstance(price, bool) or price <= 0:
            raise ConfigError(f"{where}: 'price_iec' must be a positive integer")
        params = {}
        for pname, ps in (s.get("params") or {}).items():
            pwhere = f"{where} param '{pname}'"
            if not isinstance(pname, str) or not _IDENT.match(pname):
                raise ConfigError(f"{pwhere}: names use lowercase letters, digits and _")
            if not isinstance(ps, dict) or ps.get("type") not in PARAM_TYPES:
                raise ConfigError(f"{pwhere}: 'type' must be one of {', '.join(PARAM_TYPES)}")
            params[pname] = ParamSpec(name=pname, type=ps["type"],
                                      label=str(ps.get("label") or pname),
                                      optional=bool(ps.get("optional", False)))
        spec = ServiceSpec(name=name, category=category, task_type=task_type, price_iec=price,
                           summary=str(s.get("summary") or ""), params=params,
                           settings=dict(s.get("settings") or {}))
        if spec.place_params and not places:
            raise ConfigError(f"{where}: has place parameters but the robot has no 'places'")
        services.append(spec)

    charging = d.get("charging") or {}
    if not isinstance(charging, dict):
        raise ConfigError("services.yaml: 'charging' must be a mapping")
    return RobotConfig(robot=robot, wallet=wallet, services=services, places=places,
                       charging=dict(charging))


def load_robot_config(path: str) -> RobotConfig:
    with open(path, "r") as f:
        return parse_robot_config(yaml.safe_load(f))
