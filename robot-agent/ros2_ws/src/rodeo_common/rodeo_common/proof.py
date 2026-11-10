"""
Proof conventions.

Every proof is a ROS 2 bag written by the robot's executor. It always contains:

    /rodeo/manifest   rodeo_interfaces/ProofManifest   once, at the start
    /rodeo/pose       geometry_msgs/PoseStamped        map frame, 1-2 Hz
    /rodeo/events     rodeo_interfaces/TaskEvent       arrive/depart/say/confirm/note

plus service-specific topics (delivery: /rodeo/payload_weight,
rodeo_interfaces/PayloadWeight).

The agent submits it as ``file://<absolute path>#sha256=<hex>``. The path may be
a single file or a bag directory; the hash covers its contents, so the file
cannot be swapped after submission without the oracle noticing.
"""
from __future__ import annotations

import hashlib
import os
from urllib.parse import unquote, urlparse

TOPIC_MANIFEST = "/rodeo/manifest"
TOPIC_POSE = "/rodeo/pose"
TOPIC_EVENTS = "/rodeo/events"
TOPIC_PAYLOAD_WEIGHT = "/rodeo/payload_weight"
REQUIRED_TOPICS = (TOPIC_MANIFEST, TOPIC_POSE, TOPIC_EVENTS)

_CHUNK = 1 << 20


def _hash_file(path: str, h) -> None:
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_CHUNK), b""):
            h.update(block)


def sha256_path(path: str) -> str:
    """SHA-256 of a file, or of a directory (relative names + contents, sorted)."""
    h = hashlib.sha256()
    if os.path.isdir(path):
        for root, dirs, files in os.walk(path):
            dirs.sort()
            for name in sorted(files):
                full = os.path.join(root, name)
                rel = os.path.relpath(full, path).replace(os.sep, "/")
                h.update(rel.encode() + b"\0")
                fh = hashlib.sha256()
                _hash_file(full, fh)
                h.update(fh.digest())
    else:
        _hash_file(path, h)
    return h.hexdigest()


def make_proof_uri(path: str, sha256: str | None = None) -> str:
    path = os.path.abspath(path)
    return f"file://{path}#sha256={sha256 or sha256_path(path)}"


def parse_proof_uri(uri: str) -> tuple:
    """(path, sha256 or None). Raises ValueError for anything but file:// URIs."""
    u = urlparse(uri or "")
    if u.scheme != "file":
        raise ValueError(f"not a file:// proof URI: {uri!r}")
    sha = None
    if u.fragment.startswith("sha256="):
        sha = u.fragment[len("sha256="):].lower() or None
    return unquote(u.path), sha


def proof_basename(task_id: int, robot: str, stamp: str) -> str:
    """Name for a proof bag, e.g. task12_panther_20261110T142233."""
    return f"task{int(task_id)}_{robot}_{stamp}"
