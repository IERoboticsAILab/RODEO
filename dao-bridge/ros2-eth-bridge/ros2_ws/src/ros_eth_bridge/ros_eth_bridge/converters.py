"""
converters.py - ROS 2 <-> pure-Python translation (port of bridge/converters.py).

The only module that knows both the ros_eth_msgs types and the eth.dao
dataclasses. ROS 2 messages are strictly typed, so every field is cast
explicitly (str for strings, int for integers).
"""
from __future__ import annotations

from eth.dao.query import ServiceData, TaskData
from eth.tx import TxOutcome, TxProgress
from ros_eth_msgs.msg import ServiceInfo, TaskInfo


def _s(v) -> str:
    return "" if v is None else str(v)


def _i(v) -> int:
    return 0 if v is None else int(v)


def task_data_to_msg(t: TaskData) -> TaskInfo:
    return TaskInfo(
        id=_i(t.id),
        description=_s(t.description),
        category=_s(t.category),
        task_type=_s(t.task_type),
        creator=_s(t.creator),
        executor=_s(t.executor),
        reward_wei=_s(t.reward_wei),
        status=_i(t.status),
        active=bool(t.active),
        proof_uri=_s(t.proof_uri),
        verified=bool(t.verified),
    )


def service_data_to_msg(s: ServiceData) -> ServiceInfo:
    return ServiceInfo(
        id=_i(s.id),
        name=_s(s.name),
        description=_s(s.description),
        category=_s(s.category),
        service_type=_s(s.service_type),
        price_wei=_s(s.price_wei),
        creator=_s(s.creator),
        active=bool(s.active),
        provider_type=_i(s.provider_type),
        busy=bool(s.busy),
    )


def run_action(goal_handle, action_type, dao_fn, *args, wallet=None, logger=None, **kwargs):
    """
    Run one eth.dao write function for a ROS 2 action goal and return its Result.

    Feedback mirrors every TxProgress update. On success the goal succeeds; on
    a failed or reverted transaction it is aborted (the error text goes to the
    log and to the last feedback message, since Result has no error field).
    A cancel request is honoured only before the transaction is sent; once it
    is broadcast it cannot be withdrawn.
    """
    Result, Feedback = action_type.Result, action_type.Feedback

    def failed():
        return Result(ok=False, tx_hash="", block_number=0)

    if goal_handle.is_cancel_requested:
        goal_handle.canceled()
        return failed()

    def on_progress(p: TxProgress) -> None:
        goal_handle.publish_feedback(Feedback(
            state=_s(p.state),
            tx_hash=_s(p.tx_hash),
            confirmations=_i(p.confirmations),
            error=_s(p.error),
        ))

    name = getattr(dao_fn, "__name__", "dao_fn")
    try:
        if wallet is not None:
            wallet.unlock()
        outcome: TxOutcome = dao_fn(*args, on_progress=on_progress, **kwargs)
        res = Result(ok=bool(outcome.ok), tx_hash=_s(outcome.tx_hash),
                     block_number=_i(outcome.block_number))
        if outcome.ok:
            goal_handle.succeed()
        else:
            if logger is not None:
                logger.warning(f"{name} failed: {outcome.error}")
            goal_handle.abort()
        return res
    except Exception as exc:  # noqa: BLE001 - report every failure to the client
        if logger is not None:
            logger.error(f"{name} failed: {exc}")
        try:
            on_progress(TxProgress(state="failed", tx_hash="", confirmations=0, error=str(exc)))
        except Exception:
            pass
        goal_handle.abort()
        return failed()
