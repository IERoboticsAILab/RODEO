import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from task_timer import TaskTimer, has_proof, parse_limits, start_from_env  # noqa: E402


class FakeChain:
    """Blocks with timestamps, TaskAssigned logs and the task rows."""

    def __init__(self):
        self.block, self.now = 100, 1_000_000
        self.times = {}                 # block -> timestamp
        self.logs = []                  # (block, logIndex, taskId)
        self.rows = {}                  # id -> task row
        self.log_calls = []

    def ident(self):
        return "1337:0xTM"

    def mine(self, dt=2):
        self.block += 1
        self.now += dt
        self.times[self.block] = self.now
        return self.block

    def assign(self, tid, category="Logistics"):
        b = self.mine()
        self.logs.append((b, 0, tid))
        self.rows[tid] = {"id": tid, "taskCategory": category, "status": 1, "active": True, "proofURI": "none"}

    def latest(self):
        return self.block, self.now

    def block_time(self, n):
        return self.times[n]

    def assigned_logs(self, a, b):
        self.log_calls.append((a, b))
        return [lg for lg in self.logs if a <= lg[0] <= b]

    def tasks(self):
        return [dict(r) for r in self.rows.values()]


def make(chain, unassigned, **kw):
    def unassign(tid):
        if chain.rows[tid]["status"] != 1:
            raise RuntimeError("Task not assigned")
        chain.rows[tid].update(status=0, active=False)
        unassigned.append(tid)
    return TaskTimer(chain, {"Logistics": 900}, unassign, start_block=100, log=lambda m: None, **kw)


def test_parse_limits():
    assert parse_limits("Logistics=900, Cleaning=600") == {"Logistics": 900, "Cleaning": 600}
    assert parse_limits("") == {}
    assert parse_limits("Logistics=0") == {}


def test_expires_only_after_the_limit():
    c, out = FakeChain(), []
    t = make(c, out)
    c.assign(1)
    c.mine(899)
    assert t.tick() == [] and out == []          # 899 s after the assignment
    c.mine(2)                                     # now 901 s after the assignment
    assert t.tick() == [1]
    assert c.rows[1]["status"] == 0


def test_each_task_has_its_own_clock():
    c, out = FakeChain(), []
    t = make(c, out)
    c.assign(1)
    c.mine(300)
    c.assign(2)                                   # 302 s later
    c.mine(600)                                   # task 1: 902 s, task 2: 600 s
    assert t.tick() == [1]
    c.mine(299)                                   # task 2: 899 s
    assert t.tick() == []
    c.mine(2)                                     # task 2: 901 s
    assert t.tick() == [2]


def test_not_with_a_proof_or_other_category_or_inactive():
    c, out = FakeChain(), []
    t = make(c, out)
    c.assign(1)
    c.assign(2, category="Cleaning")
    c.assign(3)
    c.rows[1]["proofURI"] = "/root/oracle/proofs/task1"
    assert has_proof(c.rows[1]) and not has_proof(c.rows[3]) and not has_proof({"proofURI": ""})
    c.rows[3]["active"] = False
    c.mine(2000)
    assert t.tick() == []


def test_reassignment_restarts_the_clock():
    c, out = FakeChain(), []
    t = make(c, out)
    c.assign(1)
    c.mine(901)
    assert t.tick() == [1]
    c.mine(50)
    c.assign(1)                                   # activated and taken again
    c.mine(500)
    assert t.tick() == []
    c.mine(401)
    assert t.tick() == [1] and out == [1, 1]


def test_failed_unassign_is_logged_and_skipped():
    c = FakeChain()
    logs = []

    def unassign(tid):
        raise RuntimeError("execution reverted: Task not assigned")
    t = TaskTimer(c, {"Logistics": 900}, unassign, start_block=100, log=logs.append)
    c.assign(1)
    c.mine(1000)
    assert t.tick() == []
    assert any("unassigning failed" in m for m in logs)


def test_scan_in_chunks_and_state_survives_restart(tmp_path):
    c, out = FakeChain(), []
    path = str(tmp_path / "timer.json")
    t = make(c, out, chunk=3, state_path=path)
    for i in range(1, 6):
        c.assign(i)
    t.tick()
    assert all(b - a <= 2 for a, b in c.log_calls)
    c.log_calls.clear()
    t2 = make(c, [], chunk=3, state_path=path)    # restart: no rescan from block 100
    assert t2.assigned == t.assigned and t2.next_block == c.block + 1
    t2.tick()
    assert c.log_calls == []


def test_annotate_fields_for_the_page():
    c, out = FakeChain(), []
    t = make(c, out)
    c.assign(1)
    c.mine(100)
    rows = c.tasks() + [{"id": 9, "taskCategory": "Logistics", "status": 0, "active": True, "proofURI": ""},
                        {"id": 8, "taskCategory": "Cleaning", "status": 0, "active": True, "proofURI": ""}]
    t.tick()
    r = {x["id"]: x for x in t.annotate(rows)}
    assert r[1]["timeoutS"] == 900 and r[1]["secondsLeft"] == 800 and r[1]["proofInTime"] is False
    assert r[9]["timeoutS"] == 900 and "deadline" not in r[9]
    assert "timeoutS" not in r[8]


def test_off_when_the_contract_has_limits():
    assert start_from_env(None, None, None, None, timeouts_on_chain=True, log=lambda m: None) is None
