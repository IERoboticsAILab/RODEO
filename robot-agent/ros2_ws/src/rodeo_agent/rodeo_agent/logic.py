"""
Decisions the agent makes, as plain functions (no ROS), so they can be tested
on their own.

    plan_service_sync  which on-chain services to keep, activate, register, deactivate
    prepare_task       turn an assigned task into the parameters the executor gets
    tasks_to_recover   tasks assigned to us that the agent must (re)run after a restart
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rodeo_common.description import parse_task_description
from rodeo_common.service_description import (
    encode_service_description, parse_service_description, resolve_task_params)
from rodeo_common.services_config import RobotConfig, ServiceSpec

WEI = 10 ** 18
STATUS_UNASSIGNED, STATUS_ASSIGNED, STATUS_EXECUTED = 0, 1, 2   # TaskManager.TaskStatus


@dataclass
class OnChainService:
    """The fields of ros_eth_msgs/ServiceInfo the agent uses."""
    id: int
    name: str
    description: str
    category: str
    service_type: str
    price_wei: int
    active: bool
    busy: bool

    @staticmethod
    def from_msg(m) -> "OnChainService":
        return OnChainService(int(m.id), m.name, m.description, m.category, m.service_type,
                              int(m.price_wei or 0), bool(m.active), bool(m.busy))


@dataclass
class SyncPlan:
    keep: dict = field(default_factory=dict)          # (category, task_type) -> service id
    activate: list = field(default_factory=list)      # service ids to reactivate
    register: list = field(default_factory=list)      # [(ServiceSpec, description)]
    deactivate: list = field(default_factory=list)    # [(service id, reason)]
    warnings: list = field(default_factory=list)


def plan_service_sync(cfg: RobotConfig, existing: list, deactivate_unknown: bool = True) -> SyncPlan:
    """
    Make the robot's on-chain services match services.yaml.

    A service is reused only if name, category, task type, price and the JSON
    description all match; otherwise a new one is registered (the contract has
    no update call) and stale ones of the same kind are deactivated, so tasks
    go to exactly one service per kind. Own services of kinds not in
    services.yaml are deactivated too: this wallet could not execute them.
    A busy service cannot be deactivated; that is reported as a warning.
    """
    plan = SyncPlan()
    wanted = {}
    for spec in cfg.services:
        wanted[(spec.category, spec.task_type)] = (spec, encode_service_description(cfg, spec))

    for key, (spec, desc) in wanted.items():
        same_kind = [s for s in existing if (s.category, s.service_type) == key]
        exact = [s for s in same_kind if s.name == spec.name and s.description == desc
                 and s.price_wei == spec.price_iec * WEI]
        exact.sort(key=lambda s: (not s.active, s.busy, s.id))      # active first, then lowest id
        chosen = exact[0] if exact else None
        if chosen is None:
            plan.register.append((spec, desc))
        else:
            plan.keep[key] = chosen.id
            if not chosen.active:
                plan.activate.append(chosen.id)
        for s in same_kind:
            if (chosen is not None and s.id == chosen.id) or not s.active:
                continue
            if s.busy:
                plan.warnings.append(f"service {s.id} ({s.name}) is outdated but busy: "
                                     "it stays active until its task is verified")
            else:
                plan.deactivate.append((s.id, "outdated duplicate of " + spec.name))

    if deactivate_unknown:
        for s in existing:
            if (s.category, s.service_type) in wanted or not s.active:
                continue
            if s.busy:
                plan.warnings.append(f"service {s.id} ({s.category}/{s.service_type}) is not in "
                                     "services.yaml but busy: left active")
            else:
                plan.deactivate.append((s.id, f"{s.category}/{s.service_type} not in services.yaml"))
    return plan


@dataclass
class PreparedTask:
    task_id: int
    spec: ServiceSpec
    params: dict
    note: str
    title: str = ""


def prepare_task(cfg: RobotConfig, task) -> tuple:
    """(PreparedTask, None) or (None, reason). ``task`` is a ros_eth_msgs/TaskInfo."""
    spec = cfg.service_for(task.category, task.task_type)
    if spec is None:
        return None, f"this robot offers no {task.category}/{task.task_type} service"
    desc = parse_task_description(task.description)
    schema = parse_service_description(encode_service_description(cfg, spec))
    params, errors = resolve_task_params(schema, desc.params)
    if errors:
        return None, "invalid task parameters: " + "; ".join(errors)
    return PreparedTask(int(task.id), spec, params, desc.note, desc.title), None


def tasks_to_recover(tasks: list, wallet: str) -> tuple:
    """
    (to_run, awaiting_verdict) among all tasks: those assigned to ``wallet`` and
    still unfinished. Without this, an assignment made while the agent was down
    would never be seen, since the bridge only publishes new events.
    """
    to_run, awaiting = [], []
    w = wallet.lower()
    for t in tasks:
        if (t.executor or "").lower() != w or int(t.status) != STATUS_ASSIGNED or not t.active:
            continue
        if t.proof_uri in ("", "none"):
            to_run.append(int(t.id))
        else:
            awaiting.append(int(t.id))
    return sorted(to_run), sorted(awaiting)


CHARGING = ("Energy", "Charging")


def choose_charging_service(services: list, own_wallet_ids: set, max_price_iec: float):
    """
    The cheapest active, non-busy charging service within budget, excluding the
    robot's own; or (None, reason). ``services`` are OnChainService objects.
    The contract settles at the service's price and keeps any excess of the
    posted reward, so the request must post exactly this price.
    """
    cands = [s for s in services if (s.category, s.service_type) == CHARGING
             and s.active and s.id not in own_wallet_ids]
    if not cands:
        return None, "no charging service is online"
    affordable = [s for s in cands if s.price_wei <= max_price_iec * WEI]
    if not affordable:
        cheapest = min(s.price_wei for s in cands) / WEI
        return None, f"cheapest charging costs {cheapest:g} IEC, above max_price_iec {max_price_iec:g}"
    free = [s for s in affordable if not s.busy] or affordable     # busy: the request queues on chain
    best = min(free, key=lambda s: (s.price_wei, s.id))
    if best.price_wei % WEI:
        return None, f"service {best.id} price is not a whole number of IEC"
    return best, None


def battery_low(percentage: float, charge_below_pct: float) -> bool:
    """BatteryState.percentage is 0..1 (NaN when unknown)."""
    return percentage == percentage and charge_below_pct > 0 and percentage * 100.0 < charge_below_pct
