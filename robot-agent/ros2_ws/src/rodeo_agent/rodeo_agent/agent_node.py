#!/usr/bin/env python3
"""
rodeo_agent - one robot's agent: connects its executor to its bridge.

Runs in the robot's namespace, next to that robot's bridge, and uses only
relative names (dao/..., rodeo/execute_task).

    start      sync on-chain services with services.yaml (reuse, reactivate,
               register, deactivate stale ones); pick up tasks assigned while
               the agent was down
    assigned   read the task, resolve its parameters, mark the robot's other
               services busy, queue it
    execute    send rodeo/execute_task to the executor, hash the proof bag it
               returns, submit file://<path>#sha256=<hash>
    verdict    on task_verified / task_rejected, bring the other services back
    charging   when the battery is low (BatteryState below charging.charge_below_pct)
               or on request (rodeo/request_charging), and the robot is idle:
               take its services offline, dock (rodeo/dock on the executor, if
               offered), post a charging task at exactly the cheapest station's
               price, and bring the services back at the verdict
    shutdown   deactivate the robot's services so no new work is assigned

While the robot is unavailable (busy with one task, or charging), its other
services are deactivated rather than marked busy: reactivating a service makes
the contract assign tasks that waited meanwhile, while clearing a busy flag
does not.

Tasks run one at a time, in arrival order. Following the project's assumption
that an online robot can finish its tasks, a task that fails or has invalid
parameters is logged and left for a person: the contract has no way for the
robot to hand it back.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import signal
import threading
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.signals import SignalHandlerOptions

from rodeo_common.proof import make_proof_uri
from rodeo_common.services_config import load_robot_config
from rodeo_interfaces.action import ExecuteTask
from ros_eth_msgs.action import ActivateService, RegisterService, RegisterTask, RemoveService, SubmitProof
from ros_eth_msgs.msg import TaskAssignment, TaskId, TaskRejection
from ros_eth_msgs.srv import GetAllServices, GetAllTasks, GetServicesByCreator, GetTask, GetTasksByCreator
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from std_srvs.srv import Trigger

from rodeo_common.description import encode_task_description

from rodeo_agent.logic import (
    CHARGING, WEI, battery_low, choose_charging_service,
    STATUS_ASSIGNED, OnChainService, plan_service_sync, prepare_task, tasks_to_recover)


class Timeout(Exception):
    pass


class RodeoAgent(Node):
    def __init__(self):
        super().__init__("rodeo_agent")
        self.declare_parameter("services_file", "")
        self.declare_parameter("proof_dir", "/root/oracle/proofs")
        self.declare_parameter("execute_timeout_sec", 1800.0)
        self.declare_parameter("bridge_timeout_sec", 60.0)
        self.declare_parameter("deactivate_unknown_services", True)
        self.declare_parameter("deactivate_on_shutdown", True)

        path = self.get_parameter("services_file").value or os.environ.get("RODEO_SERVICES_FILE", "")
        if not path:
            raise RuntimeError("set the services_file parameter (or RODEO_SERVICES_FILE)")
        self.cfg = load_robot_config(path)
        self.proof_dir = self.get_parameter("proof_dir").value
        self.exec_timeout = float(self.get_parameter("execute_timeout_sec").value)
        self.log = self.get_logger()

        cb = ReentrantCallbackGroup()
        self._a = {
            "register": ActionClient(self, RegisterService, "dao/register_service_action", callback_group=cb),
            "activate": ActionClient(self, ActivateService, "dao/activate_service_action", callback_group=cb),
            "remove": ActionClient(self, RemoveService, "dao/remove_service_action", callback_group=cb),
            "task": ActionClient(self, RegisterTask, "dao/register_task_action", callback_group=cb),
            "submit": ActionClient(self, SubmitProof, "dao/submit_proof_action", callback_group=cb),
            "execute": ActionClient(self, ExecuteTask, "rodeo/execute_task", callback_group=cb),
        }
        self._s = {
            "services": self.create_client(GetServicesByCreator, "dao/get_services_by_creator", callback_group=cb),
            "task": self.create_client(GetTask, "dao/get_task_by_id", callback_group=cb),
            "tasks": self.create_client(GetAllTasks, "dao/get_all_tasks", callback_group=cb),
            "all_services": self.create_client(GetAllServices, "dao/get_all_services", callback_group=cb),
            "my_tasks": self.create_client(GetTasksByCreator, "dao/get_tasks_by_creator", callback_group=cb),
            "dock": self.create_client(Trigger, "rodeo/dock", callback_group=cb),
        }
        self.create_subscription(TaskAssignment, "dao/task_assigned", self._on_assigned, 50, callback_group=cb)
        self.create_subscription(TaskId, "dao/task_verified", self._on_verified, 50, callback_group=cb)
        self.create_subscription(TaskRejection, "dao/task_rejected", self._on_rejected, 50, callback_group=cb)

        self.service_ids: dict = {}        # (category, task_type) -> on-chain service id
        self.work: "queue.Queue" = queue.Queue()
        self.seen: set = set()             # task ids queued or done (dedupe)
        self.awaiting: dict = {}           # task id -> own service ids taken offline for it
        self.charging_task = None          # id of our pending charging task

        # charging (services.yaml `charging:`); 0 disables the battery trigger
        ch = self.cfg.charging
        self.max_charge_price = float(ch.get("max_price_iec", 0))
        self.charge_below = float(ch.get("charge_below_pct", 0))
        self.battery_pct = float("nan")
        self._charge_cooldown_until = 0.0
        if ch.get("battery_topic") and self.charge_below > 0:
            self.create_subscription(BatteryState, ch["battery_topic"], self._on_battery, 10,
                                     callback_group=cb)
        self.create_service(Trigger, "rodeo/request_charging", self._on_request_charging,
                            callback_group=cb)
        self.charged_pub = self.create_publisher(String, "rodeo/charged", 10)
        self.lock = threading.Lock()
        self.stopping = threading.Event()

    # ================================================================== ROS call helpers
    def _call(self, name: str, request, timeout: float = 15.0):
        cli = self._s[name]
        if not cli.wait_for_service(timeout_sec=timeout):
            raise Timeout(f"service {cli.srv_name} not available")
        done, box = threading.Event(), {}
        fut = cli.call_async(request)
        fut.add_done_callback(lambda f: (box.setdefault("r", f.result()), done.set()))
        if not done.wait(timeout):
            raise Timeout(f"{cli.srv_name} did not answer in {timeout:.0f} s")
        return box["r"]

    def _action(self, name: str, goal, timeout: float, feedback=None):
        cli = self._a[name]
        if not cli.wait_for_server(timeout_sec=min(timeout, 15.0)):
            raise Timeout(f"action {name} ({cli._action_name}) not available")
        done, box = threading.Event(), {}

        def on_result(f):
            box["result"] = f.result().result
            done.set()

        def on_goal(f):
            gh = f.result()
            if not gh.accepted:
                box["result"] = None
                done.set()
            else:
                gh.get_result_async().add_done_callback(on_result)

        cli.send_goal_async(goal, feedback_callback=feedback).add_done_callback(on_goal)
        if not done.wait(timeout):
            raise Timeout(f"action {name} did not finish in {timeout:.0f} s")
        return box["result"]

    def _tx(self, name: str, goal, what: str) -> bool:
        """Run a bridge write action (RegisterService, SubmitProof, ...); True on success."""
        goal.min_confirmations = 1
        res = self._action(name, goal, 90.0)
        if res is None or not res.ok:
            self.log.error(f"{what}: transaction failed")
            return False
        self.log.info(f"{what}: ok (block {res.block_number})")
        return True

    def _own_services(self) -> list:
        res = self._call("services", GetServicesByCreator.Request(creator=""))
        if not res.ok:
            raise RuntimeError("get_services_by_creator failed")
        return [OnChainService.from_msg(s) for s in res.services]

    # ================================================================== start-up
    def startup(self) -> None:
        self.log.info(f"robot '{self.cfg.robot}', wallet {self.cfg.wallet}, "
                      f"{len(self.cfg.services)} service(s), proofs in {self.proof_dir}")
        t = float(self.get_parameter("bridge_timeout_sec").value)
        if not self._s["services"].wait_for_service(timeout_sec=t):
            raise Timeout(f"bridge not found in namespace '{self.get_namespace()}' after {t:.0f} s")
        self.sync_services()
        self.recover_tasks()
        self.log.info("ready - waiting for assignments")

    def sync_services(self) -> None:
        plan = plan_service_sync(self.cfg, self._own_services(),
                                 bool(self.get_parameter("deactivate_unknown_services").value))
        for w in plan.warnings:
            self.log.warning(w)
        for sid, why in plan.deactivate:            # first, so new tasks can't land on stale services
            self._tx("remove", RemoveService.Goal(service_id=sid), f"deactivate service {sid} ({why})")
        for sid in plan.activate:
            self._tx("activate", ActivateService.Goal(service_id=sid), f"reactivate service {sid}")
        for spec, desc in plan.register:
            g = RegisterService.Goal(name=spec.name, description=desc, category=spec.category,
                                     service_type=spec.task_type, price=str(spec.price_iec),
                                     provider_type=0)
            self._tx("register", g, f"register service '{spec.name}' ({spec.category}/{spec.task_type}, "
                                    f"{spec.price_iec} IEC)")
        self.service_ids = dict(plan.keep)
        if plan.register:                            # read back the ids of new services
            after = plan_service_sync(self.cfg, self._own_services(), False)
            self.service_ids = dict(after.keep)
        for spec in self.cfg.services:
            sid = self.service_ids.get((spec.category, spec.task_type))
            self.log.info(f"service '{spec.name}' -> id {sid if sid is not None else 'MISSING'}")

    def recover_tasks(self) -> None:
        res = self._call("tasks", GetAllTasks.Request())
        if not res.ok:
            self.log.warning("get_all_tasks failed: no recovery of earlier assignments")
            return
        to_run, awaiting = tasks_to_recover(res.tasks, self.cfg.wallet)
        for tid in awaiting:
            self.log.info(f"task {tid}: proof already submitted, waiting for the oracle")
            with self.lock:
                self.seen.add(tid)
                self.awaiting.setdefault(tid, set())
        for tid in to_run:
            self.log.info(f"task {tid}: assigned while the agent was down - queued")
            self._enqueue(tid)

    # ================================================================== events
    def _enqueue(self, task_id: int) -> None:
        with self.lock:
            if task_id in self.seen:
                return
            self.seen.add(task_id)
        self.work.put(("task", task_id))

    def _on_assigned(self, msg: TaskAssignment) -> None:
        if msg.executor.lower() != self.cfg.wallet.lower():
            return                                   # the bridge filters too; belt and braces
        self.log.info(f"task {msg.task_id} assigned (reward {int(msg.reward_wei) / 1e18:g} IEC)")
        self._enqueue(int(msg.task_id))

    def _on_verified(self, msg: TaskId) -> None:
        self._verdict(int(msg.task_id), True, "")

    def _on_rejected(self, msg: TaskRejection) -> None:
        self._verdict(int(msg.task_id), False, msg.reason)

    def _verdict(self, task_id: int, ok: bool, reason: str) -> None:
        with self.lock:
            if task_id not in self.awaiting:
                return
        self.work.put(("verdict", (task_id, ok, reason)))

    # ================================================================== worker
    def _on_battery(self, msg: BatteryState) -> None:
        self.battery_pct = float(msg.percentage)

    def _on_request_charging(self, _req, res):
        if self.charging_task is not None:
            res.success, res.message = False, f"charging task {self.charging_task} already pending"
        elif self.max_charge_price <= 0:
            res.success, res.message = False, "charging.max_price_iec not set in services.yaml"
        else:
            self.work.put(("charge", "requested"))
            res.success, res.message = True, "charging request queued"
        return res

    def _idle(self) -> bool:
        with self.lock:
            return self.work.empty() and not self.awaiting and self.charging_task is None

    def run(self) -> None:
        while not self.stopping.is_set():
            try:
                kind, arg = self.work.get(timeout=0.5)
            except queue.Empty:
                if (battery_low(self.battery_pct, self.charge_below) and self._idle()
                        and time.monotonic() > self._charge_cooldown_until):
                    self.work.put(("charge", f"battery at {self.battery_pct * 100:.0f} %"))
                continue
            try:
                if kind == "task":
                    self.execute(arg)
                elif kind == "charge":
                    self.request_charging(arg)
                else:
                    self.finish(*arg)
            except Exception as e:  # noqa: BLE001 - keep serving later tasks
                self.log.error(f"{kind} {arg}: {e}")

    def _pause(self, ids, why: str) -> set:
        """Take services offline (deactivate); returns those that were taken offline."""
        paused = set()
        if not ids:
            return paused
        state = {s.id: s for s in self._own_services()}
        for sid in sorted(ids):
            s = state.get(sid)
            if s is None or not s.active:
                continue
            if s.busy:
                self.log.warning(f"service {sid} is busy and stays online ({why})")
                continue
            if self._tx("remove", RemoveService.Goal(service_id=sid), f"take service {sid} offline ({why})"):
                paused.add(sid)
        return paused

    def _resume(self, ids, why: str) -> None:
        """Bring services back online; the contract then assigns tasks that waited."""
        for sid in sorted(ids):
            self._tx("activate", ActivateService.Goal(service_id=sid), f"bring service {sid} back ({why})")

    def execute(self, task_id: int) -> None:
        res = self._call("task", GetTask.Request(task_id=task_id))
        if not res.ok:
            self.log.error(f"task {task_id}: could not read it from the chain")
            return
        task = res.task
        if task.executor.lower() != self.cfg.wallet.lower() or int(task.status) != STATUS_ASSIGNED:
            self.log.warning(f"task {task_id}: no longer assigned to this robot - skipped")
            return
        prepared, why = prepare_task(self.cfg, task)
        if prepared is None:
            self.log.error(f"task {task_id}: {why} - not executed; it stays assigned for a person to resolve")
            return

        own = self.service_ids.get((task.category, task.task_type))
        siblings = self._pause({sid for sid in self.service_ids.values() if sid is not None and sid != own},
                               f"robot busy with task {task_id}")

        goal = ExecuteTask.Goal(task_id=task_id, category=task.category, task_type=task.task_type,
                                params_json=json.dumps(prepared.params, sort_keys=True),
                                note=prepared.note, executor=self.cfg.wallet, robot=self.cfg.robot,
                                proof_dir=self.proof_dir)
        name = f" '{prepared.title}'" if prepared.title else ""
        self.log.info(f"task {task_id}{name}: executing {prepared.spec.name} with {goal.params_json}")
        t0 = time.monotonic()

        def feedback(fb):
            f = fb.feedback
            self.log.info(f"task {task_id}: {f.stage}" + (f" - {f.detail}" if f.detail else ""))

        try:
            result = self._action("execute", goal, self.exec_timeout, feedback)
        except Timeout as e:
            result = None
            self.log.error(f"task {task_id}: {e}")
        if result is None or not result.success:
            msg = result.message if result is not None else "no result"
            self.log.error(f"task {task_id}: execution failed ({msg}) - left for a person to resolve")
            self._resume(siblings, f"task {task_id} failed")
            return
        if not result.proof_path or not os.path.exists(result.proof_path):
            self.log.error(f"task {task_id}: executor returned proof '{result.proof_path}', "
                           "which this agent cannot read (is the proof folder shared?)")
            self._resume(siblings, f"task {task_id} has no proof")
            return

        uri = make_proof_uri(result.proof_path)
        self.log.info(f"task {task_id}: done in {time.monotonic() - t0:.0f} s, proof {uri}")
        with self.lock:
            self.awaiting[task_id] = siblings
        if not self._tx("submit", SubmitProof.Goal(task_id=task_id, proof_uri=uri),
                        f"task {task_id}: submit proof"):
            with self.lock:
                self.awaiting.pop(task_id, None)
            self._resume(siblings, f"task {task_id} proof not submitted")
            return
        self.log.info(f"task {task_id}: waiting for the oracle")

    def finish(self, task_id: int, ok: bool, reason: str) -> None:
        with self.lock:
            siblings = self.awaiting.pop(task_id, set())
            charging = task_id == self.charging_task
            if charging:
                self.charging_task = None
        if charging:
            self.log.info(f"charging task {task_id}: " + ("VERIFIED - station paid" if ok else
                          f"REJECTED ({reason or 'no reason'}) - escrow refunded"))
            self.charged_pub.publish(String(data=json.dumps({"task_id": task_id, "ok": ok})))
            if not ok:
                self._charge_cooldown_until = time.monotonic() + 60.0
            self._resume(siblings, f"charging task {task_id} settled")
            return
        if ok:
            self.log.info(f"task {task_id}: VERIFIED - reward paid")
        else:
            self.log.warning(f"task {task_id}: REJECTED by the oracle ({reason or 'no reason given'}); "
                             "the contract refunded the creator and deactivated the task")
        self._resume(siblings, f"task {task_id} settled")

    # ================================================================== charging
    def request_charging(self, reason: str) -> None:
        if self.charging_task is not None:
            return
        if self.max_charge_price <= 0:
            self.log.warning("charging requested but charging.max_price_iec is not set")
            return
        res = self._call("all_services", GetAllServices.Request())
        own_ids = {sid for sid in self.service_ids.values() if sid is not None}
        station, why = choose_charging_service([OnChainService.from_msg(m) for m in res.services],
                                               own_ids, self.max_charge_price) if res.ok else (None, "query failed")
        if station is None:
            self.log.warning(f"charging ({reason}): {why}; retrying in 60 s")
            self._charge_cooldown_until = time.monotonic() + 60.0
            return
        price = station.price_wei // WEI
        self.log.info(f"charging ({reason}): station service {station.id} '{station.name}', {price} IEC")

        paused = self._pause(own_ids, "charging")
        if self._s["dock"].wait_for_service(timeout_sec=2.0):
            try:
                r = self._call("dock", Trigger.Request(), timeout=600.0)
                self.log.info(f"dock: {'ok' if r.success else 'FAILED'} {r.message}")
                if not r.success:
                    self._resume(paused, "dock failed")
                    self._charge_cooldown_until = time.monotonic() + 60.0
                    return
            except Timeout as e:
                self.log.error(f"dock: {e}")
                self._resume(paused, "dock timed out")
                return
        else:
            self.log.info("executor offers no rodeo/dock service: assuming the robot is docked")

        desc = encode_task_description({"robot": self.cfg.robot, "wallet": self.cfg.wallet}, f"charge request ({reason})")
        if not self._tx("task", RegisterTask.Goal(description=desc, category=CHARGING[0], task_type=CHARGING[1],
                                                  reward=str(price)), f"post charging task ({price} IEC)"):
            self._resume(paused, "charging request failed")
            self._charge_cooldown_until = time.monotonic() + 60.0
            return
        mine = self._call("my_tasks", GetTasksByCreator.Request(creator=""))
        ids = [int(t.id) for t in mine.tasks if (t.category, t.task_type) == CHARGING] if mine.ok else []
        if not ids:
            self.log.error("charging task posted but not found on chain")
            self._resume(paused, "charging task not found")
            return
        tid = max(ids)
        with self.lock:
            self.charging_task = tid
            self.awaiting[tid] = paused
        self.log.info(f"charging task {tid} posted; waiting for the station and the oracle")

    # ================================================================== shutdown
    def shutdown_services(self) -> None:
        if not self.get_parameter("deactivate_on_shutdown").value:
            return
        try:
            own = {s.id: s for s in self._own_services()}
        except Exception as e:  # noqa: BLE001
            self.log.warning(f"shutdown: could not read services ({e}); left as they are")
            return
        for sid in sorted(set(self.service_ids.values())):
            s = own.get(sid)
            if s is None or not s.active:
                continue
            if s.busy:
                self.log.warning(f"shutdown: service {sid} is busy, left active")
                continue
            try:
                self._tx("remove", RemoveService.Goal(service_id=sid), f"shutdown: deactivate service {sid}")
            except Exception as e:  # noqa: BLE001
                self.log.warning(f"shutdown: deactivating service {sid} failed: {e}")


def main(args=None):
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] [%(name)s]: %(message)s")
    # Own signal handling: on SIGINT/SIGTERM the agent still needs ROS to
    # deactivate its services before shutting down.
    rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
    node = RodeoAgent()
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    spin = threading.Thread(target=executor.spin, daemon=True)
    spin.start()

    def on_signal(signum, _frame):
        node.log.info(f"signal {signum}: stopping")
        node.stopping.set()
    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    code = 0
    try:
        node.startup()
        node.run()
    except Exception as e:  # noqa: BLE001
        node.log.error(f"fatal: {e}")
        code = 1
    finally:
        node.shutdown_services()
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
