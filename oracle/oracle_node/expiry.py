"""
Task execution time limits. The contract cannot act by itself, so the oracle sends
TaskManager.expireTask for assigned tasks that passed their category's limit
(Organization.setTaskTimeout, e.g. Logistics 900 s) without a proof. The contract
then unassigns the task, refunds the creator, frees the service and deactivates the
task; the bridge publishes TaskUnassigned and the robot's agent cancels the run.

Only block times are compared (on chain), so no clock on a robot or server matters.
EXPIRE_EVERY_SEC (default 15; 0 = off) sets how often the oracle looks.
"""
import time


def run_expiry_sweeper(chain, every_s: float, log=print, stop=None) -> None:
    if every_s <= 0:
        log("task expiry: off (EXPIRE_EVERY_SEC=0)")
        return
    log(f"task expiry: checking assigned tasks every {every_s:.0f} s")
    while stop is None or not stop.is_set():
        try:
            for tid, deadline in chain.expire_overdue():
                log(f"task {tid}: EXPIRED - no proof by its deadline (block time {deadline}); "
                    "unassigned, creator refunded")
        except Exception as e:  # noqa: BLE001
            if "isExpired" in str(e) or isinstance(e, AttributeError) or "ABIFunctionNotFound" in type(e).__name__:
                log("task expiry: the deployed TaskManager has no execution timeouts - sweeper off")
                return
            log(f"task expiry: check failed: {e}")
        time.sleep(every_s)
