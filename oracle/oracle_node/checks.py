"""
Checks every RODEO proof must pass before its service's validator runs.

    manifest     exactly one, format version 1, and it names this task, its
                 executor, category and task type
    parameters   the manifest's parameters are the task's (with the service's
                 defaults filled in): the robot did what was asked
    time         every message lies between the task's assignment and the proof
                 submission (block times), within a clock tolerance
    hash         the file still has the hash in the URI, and no earlier task
                 used it
"""
from __future__ import annotations

import json
import os
import threading

from rodeo_common.description import parse_task_description
from rodeo_common.service_description import parse_service_description, resolve_task_params

from .validators import Verdict

FORMAT_VERSION = 1


class UsedProofs:
    """Hashes of proofs already accepted or rejected, kept on disk across restarts."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        try:
            with open(path) as f:
                self._used = json.load(f)
        except (OSError, ValueError):
            self._used = {}

    def task_for(self, sha: str):
        with self._lock:
            return self._used.get(sha)

    def record(self, sha: str, task_id: int):
        with self._lock:
            self._used[sha] = task_id
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._used, f, indent=1)
            os.replace(tmp, self.path)


def check_rodeo_proof(task, proof, window, service_desc, sha_ok, reused_by, tolerance_s) -> Verdict:
    """Shared checks. ``window`` is (assigned_ts, submitted_ts)."""
    v = Verdict(ok=True)
    v.check(sha_ok, "proof hash matches the URI", "proof changed after submission (hash mismatch)")
    v.check(reused_by is None, "proof not used before" if reused_by is None
            else f"proof already used for task {reused_by}", "proof reused from another task")

    m = proof.manifest
    if not v.check(m is not None, f"one manifest ({len(proof.manifests)} found)", "proof has no single manifest"):
        return v
    v.check(int(m.format_version) == FORMAT_VERSION, f"manifest format {m.format_version}",
            f"unsupported manifest format {m.format_version}")
    v.check(int(m.task_id) == task.id, f"manifest task id {m.task_id}",
            f"proof is for task {m.task_id}, not {task.id}")
    v.check(m.executor.lower() == task.executor.lower(), f"manifest executor {m.executor}",
            "proof executor is not the task's executor")
    v.check((m.category, m.task_type) == (task.category, task.task_type),
            f"manifest service {m.category}/{m.task_type}", "proof is for another kind of task")

    if service_desc is not None:
        schema = parse_service_description(service_desc)
        expected, errs = resolve_task_params(schema, parse_task_description(task.description).params)
        same = not errs and proof.params == expected
        v.check(same, "parameters match the task" if same else
                f"parameters differ: task {expected if not errs else errs}, proof {proof.params}",
                "proof parameters do not match the task")

    assigned, submitted = window
    if assigned is None or submitted is None:
        v.check(False, "task assignment/submission times not found on chain", "no task time window")
    elif proof.log_times:
        lo, hi = min(proof.log_times), max(proof.log_times)
        inside = lo >= assigned - tolerance_s and hi <= submitted + tolerance_s
        v.check(inside, f"recorded {lo - assigned:+.1f} s .. {hi - submitted:+.1f} s relative to "
                        f"assignment/submission (tolerance {tolerance_s:.0f} s)",
                "proof recorded outside the task's time window")
    else:
        v.check(False, "proof has no messages", "empty proof")
    return v
