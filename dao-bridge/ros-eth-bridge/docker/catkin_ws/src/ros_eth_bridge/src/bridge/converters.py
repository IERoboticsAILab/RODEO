"""
bridge/converters.py — ROS ↔ pure-Python data translation.

This module is the single place that knows about *both* ros_eth_msgs types and
eth.dao dataclasses.  Keep the mapping logic here so that node files stay thin
wiring code.

Exports
-------
task_data_to_msg(t: TaskData) -> TaskInfo
service_data_to_msg(s: ServiceData) -> ServiceInfo
run_action(action_server, ResultCls, FeedbackCls, dao_fn, *args,
           wallet=None, **kwargs) -> None
"""

from __future__ import annotations

import rospy

from eth.dao.query import TaskData, ServiceData
from eth.tx import TxProgress, TxOutcome
from eth.wallet import Wallet

from ros_eth_msgs.msg import TaskInfo, ServiceInfo


# ---------------------------------------------------------------------------
# Data converters — eth.dao dataclass → ROS message
# ---------------------------------------------------------------------------

def task_data_to_msg(t: TaskData) -> TaskInfo:
    """Convert a :class:`~eth.dao.query.TaskData` to a ``TaskInfo`` ROS msg."""
    msg = TaskInfo()
    msg.id          = t.id
    msg.description = t.description
    msg.category    = t.category
    msg.task_type   = t.task_type
    msg.creator     = t.creator
    msg.reward_wei  = str(t.reward_wei)
    msg.status      = t.status
    msg.executor    = t.executor
    msg.active      = t.active
    msg.proof_uri   = t.proof_uri
    msg.verified    = t.verified
    return msg


def service_data_to_msg(s: ServiceData) -> ServiceInfo:
    """Convert a :class:`~eth.dao.query.ServiceData` to a ``ServiceInfo`` ROS msg."""
    msg = ServiceInfo()
    msg.id            = s.id
    msg.name          = s.name
    msg.description   = s.description
    msg.category      = s.category
    msg.service_type  = s.service_type
    msg.price_wei     = str(s.price_wei)
    msg.creator       = s.creator
    msg.active        = s.active
    msg.provider_type = s.provider_type
    msg.busy          = s.busy
    return msg


# ---------------------------------------------------------------------------
# Generic action runner
# ---------------------------------------------------------------------------

def run_action(
    action_server,
    ResultCls,
    FeedbackCls,
    dao_fn,
    *args,
    wallet: Wallet | None = None,
    **kwargs,
) -> None:
    """
    Call a DAO write function and map its outcome onto a ROS action server.

    Parameters
    ----------
    action_server:
        A ``rospy`` ``SimpleActionServer`` instance that is currently executing.
    ResultCls:
        The ROS action result class (e.g. ``RegisterTaskResult``).
    FeedbackCls:
        The ROS action feedback class (e.g. ``RegisterTaskFeedback``).
    dao_fn:
        Callable from ``eth.dao.*``.  Must accept ``on_progress`` as a keyword
        argument and return a :class:`~eth.tx.TxOutcome`.
    *args:
        Positional arguments forwarded to *dao_fn*.
    wallet:
        Optional :class:`~eth.wallet.Wallet`.  If supplied it is unlocked before
        *dao_fn* is called (dao functions also unlock internally, but doing it
        here surfaces passphrase prompts before the tx is built).
    **kwargs:
        Keyword arguments forwarded to *dao_fn*.  ``on_progress`` must **not**
        be in *kwargs* — it is set by this function.
    """
    # Check if goal was preempted before starting
    if action_server.is_preempt_requested():
        rospy.loginfo("Goal preempted before execution started")
        action_server.set_preempted()
        return
    
    pubfb = action_server.publish_feedback

    def on_progress(p: TxProgress) -> None:
        # Check for preempt during execution
        if action_server.is_preempt_requested():
            rospy.logwarn("Goal preempted during execution - aborting")
            action_server.set_preempted(ResultCls(ok=False, tx_hash="", block_number=0))
            return
            
        pubfb(FeedbackCls(
            state=p.state,
            tx_hash=p.tx_hash,
            confirmations=p.confirmations,
            error=p.error,
        ))

    try:
        if wallet is not None:
            wallet.unlock()
        outcome: TxOutcome = dao_fn(*args, on_progress=on_progress, **kwargs)
        
        # Check for preempt after execution but before setting result
        if action_server.is_preempt_requested():
            rospy.logwarn("Goal preempted after execution completed")
            action_server.set_preempted()
            return
            
        res = ResultCls(
            ok=bool(outcome.ok),
            tx_hash=outcome.tx_hash,
            block_number=int(outcome.block_number),
        )
        if outcome.ok:
            action_server.set_succeeded(res)
        else:
            action_server.set_aborted(res, outcome.error)
    except Exception as exc:
        rospy.logerr("run_action %s failed: %s", dao_fn.__name__, exc)
        on_progress(TxProgress(state="failed", tx_hash="", confirmations=0, error=str(exc)))
        
        # Check if preempted even on exception
        if action_server.is_preempt_requested():
            action_server.set_preempted(ResultCls(ok=False, tx_hash="", block_number=0))
        else:
            action_server.set_aborted(
                ResultCls(ok=False, tx_hash="", block_number=0), str(exc)
            )
