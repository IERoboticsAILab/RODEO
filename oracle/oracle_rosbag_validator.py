# oracle_ros1_bag_validator.py
import os
import sys
import time
import json
import math
import signal
import subprocess
from threading import Lock

import rospy
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState

# -------------- user config --------------
# Rosbag path can be provided by env or argv[1]
BAG_PATH = os.environ.get("BAG_PATH", "")

# Playback rate
PLAY_RATE = float(os.environ.get("PLAY_RATE", "1.0"))

# Motion detection windows
MIN_STATE_SEC = float(os.environ.get("MIN_STATE_SEC", "0.5"))
# Position change threshold for odom_mocap move or stop detection
POS_EPS = float(os.environ.get("POS_EPS", "0.002"))  # meters

# Arm movement thresholds
ARM_POS_EPS = float(os.environ.get("ARM_POS_EPS", "0.005"))  # rad per sample to consider moving
ARM_TOTAL_DELTA_TOL = float(os.environ.get("ARM_TOTAL_DELTA_TOL", "0.05"))  # net rad change from initial
MIN_ARM_STATE_SEC = float(os.environ.get("MIN_ARM_STATE_SEC", "0.0"))

# Minimum total path to consider that the base moved at all
MIN_PATH_METERS = float(os.environ.get("MIN_PATH_METERS", "0.10"))

# Arm joint state topic to use
JOINT_TOPIC = os.environ.get("JOINT_TOPIC", "/vx300s/joint_states")

DISPOSAL_TOPIC = "/disposal_event"
# -------------- end config --------------

_bag_proc = None
_shutdown = False

# Base motion tracking via /odom_mocap
odom_lock = Lock()
last_pos = None  # (x, y)
last_t = None    # float seconds
path_len = 0.0
segments = []     # list of dicts: {"state": "moving"|"stopped", "t0": float, "t1": float}
cur_state = None
cur_t0 = None

# Arm movement tracking
js_lock = Lock()
arm_last_map = None
arm_last_t = None
arm_init_map = None
arm_segments = []   # same schema as base segments
arm_cur_state = None
arm_cur_t0 = None
arm_move_count = 0           # counted by transitions into moving
arm_episode_count = 0        # internal counter for transitions
arm_net_delta = 0.0
arm_joint_net = {}

# Disposal event tracking
event_lock = Lock()
disposal_correct_seen = False
last_disposal = None


# ---------------- rosbag playback ----------------

def _build_rosbag_cmd(bag_path):
    setup = os.environ.get("ROS_SETUP", "")
    distro = os.environ.get("ROS_DISTRO", "")
    if setup:
        return f"source {setup} && rosbag play '{bag_path}' -r {PLAY_RATE} --clock"
    setup_guess = f"/opt/ros/{distro}/setup.bash" if distro else ""
    if setup_guess and os.path.exists(setup_guess):
        return f"source {setup_guess} && rosbag play '{bag_path}' -r {PLAY_RATE} --clock"
    return f"rosbag play '{bag_path}' -r {PLAY_RATE} --clock"


def start_bag_play(bag_path):
    """Plays the bag and publishes /clock. Uses bash -lc so the ROS environment is sourced."""
    global _bag_proc
    cmd_str = _build_rosbag_cmd(bag_path)
    rospy.loginfo("rosbag command: %s", cmd_str)
    _bag_proc = subprocess.Popen(
        ["bash", "-lc", cmd_str],
        stdout=None,
        stderr=None,
        preexec_fn=os.setsid,
        executable="/bin/bash",
    )
    rospy.loginfo("Started rosbag play at rate %.2f", PLAY_RATE)


def stop_bag():
    global _bag_proc
    p = _bag_proc
    _bag_proc = None
    if p is None:
        return
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except Exception:
        pass
    time.sleep(0.5)
    try:
        os.killpg(os.getpgid(p.pid), signal.SIGKILL)
    except Exception:
        pass


# ---------------- signal handling ----------------

def sig_handler(sig, frame):
    global _shutdown
    _shutdown = True
    stop_bag()
    rospy.signal_shutdown("signal")


# ---------------- helpers ----------------

def _get_time(msg):
    try:
        t = msg.header.stamp.to_sec()
        # Guard against non-increasing stamps, fall back to wall time
        if t == 0.0:
            return rospy.Time.now().to_sec()
        return t
    except Exception:
        return rospy.Time.now().to_sec()


def _extract_pose_and_time_from_odom(msg):
    x = msg.pose.pose.position.x
    y = msg.pose.pose.position.y
    t = _get_time(msg)
    return x, y, t


def _advance_state_bool(cur_state_name, cur_t0_name, segments_name, t_now, moving):
    desired = "moving" if moving else "stopped"
    cur_state_val = globals()[cur_state_name]
    cur_t0_val = globals()[cur_t0_name]
    if cur_state_val is None:
        globals()[cur_state_name] = desired
        globals()[cur_t0_name] = t_now
        return
    if desired != cur_state_val:
        if cur_t0_val is not None and t_now > cur_t0_val:
            globals()[segments_name].append({"state": cur_state_val, "t0": cur_t0_val, "t1": t_now})
        globals()[cur_state_name] = desired
        globals()[cur_t0_name] = t_now


def _advance_arm_state(t_now, moving):
    """Like _advance_state_bool, but also counts transitions into moving as movement episodes."""
    global arm_cur_state, arm_cur_t0, arm_segments, arm_episode_count
    desired = "moving" if moving else "stopped"
    if arm_cur_state is None:
        arm_cur_state = desired
        arm_cur_t0 = t_now
        if desired == "moving":
            arm_episode_count += 1
        return
    if desired != arm_cur_state:
        if arm_cur_t0 is not None and t_now > arm_cur_t0:
            arm_segments.append({"state": arm_cur_state, "t0": arm_cur_t0, "t1": t_now})
        if desired == "moving":
            arm_episode_count += 1
        arm_cur_state = desired
        arm_cur_t0 = t_now


def _finalize_segments(cur_state_name, cur_t0_name, last_t_value, segments_name, min_sec):
    cur_state_val = globals()[cur_state_name]
    cur_t0_val = globals()[cur_t0_name]
    segs = globals()[segments_name]
    if cur_state_val is not None and cur_t0_val is not None and last_t_value is not None and last_t_value > cur_t0_val:
        segs.append({"state": cur_state_val, "t0": cur_t0_val, "t1": last_t_value})
    segs[:] = [s for s in segs if (s["t1"] - s["t0"]) >= min_sec]


def _has_stopped_moved_stopped(segs):
    reduced = []
    for s in segs:
        if not reduced or s["state"] != reduced[-1]:
            reduced.append(s["state"])
    for i in range(len(reduced) - 2):
        if reduced[i] == "stopped" and reduced[i+1] == "moving" and reduced[i+2] == "stopped":
            return True
    return False


# ---------------- callbacks ----------------

def odom_cb(msg: Odometry):
    global last_pos, last_t, path_len
    x, y, t = _extract_pose_and_time_from_odom(msg)
    with odom_lock:
        if last_pos is not None and last_t is not None and t >= last_t:
            dx = x - last_pos[0]
            dy = y - last_pos[1]
            dist = math.hypot(dx, dy)
            path_len += dist
            moving_now = dist > POS_EPS
            _advance_state_bool("cur_state", "cur_t0", "segments", t, moving_now)
        last_pos = (x, y)
        last_t = t


def _map_from_joint_state(msg: JointState):
    return {n: p for n, p in zip(msg.name, msg.position)}


def _net_delta_from_initial(cur_map, init_map):
    if not init_map:
        return 0.0
    total = 0.0
    for jn, p0 in init_map.items():
        if jn in cur_map:
            total += abs(cur_map[jn] - p0)
    return total


def joint_cb(msg: JointState):
    global arm_last_map, arm_last_t, arm_init_map, arm_net_delta, arm_joint_net
    new_map = _map_from_joint_state(msg)
    t = _get_time(msg)
    with js_lock:
        if arm_init_map is None:
            arm_init_map = dict(new_map)
            arm_joint_net = {jn: 0.0 for jn in new_map.keys()}
        if arm_last_map is not None and arm_last_t is not None and t >= arm_last_t:
            max_step = 0.0
            for jn, pos in new_map.items():
                if jn in arm_last_map:
                    d = abs(pos - arm_last_map[jn])
                    if d > max_step:
                        max_step = d
                    # update per joint net change from initial
                    arm_joint_net[jn] = max(arm_joint_net.get(jn, 0.0), abs(pos - arm_init_map.get(jn, pos)))
            moving_now = max_step > ARM_POS_EPS
            _advance_arm_state(t, moving_now)
        elif arm_last_map is None:
            # First sample, treat as stopped relative to itself
            _advance_arm_state(t, False)
        arm_last_map = new_map
        arm_last_t = t
        arm_net_delta = max(arm_net_delta, _net_delta_from_initial(new_map, arm_init_map))


def disposal_cb(msg: String):
    global disposal_correct_seen, last_disposal
    try:
        data = json.loads(msg.data)
        last_disposal = data
        if bool(data.get("correct", False)):
            disposal_correct_seen = True
    except Exception:
        pass


# ---------------- validation ----------------

def _finalize_all_segments():
    _finalize_segments("cur_state", "cur_t0", last_t, "segments", MIN_STATE_SEC)
    _finalize_segments("arm_cur_state", "arm_cur_t0", arm_last_t, "arm_segments", MIN_ARM_STATE_SEC)


def validate():
    global arm_move_count
    _finalize_all_segments()

    # Base
    with odom_lock:
        pl = path_len
    base_path_ok = pl >= MIN_PATH_METERS
    two_stops_ok = _has_stopped_moved_stopped(segments)
    base_ok = base_path_ok and two_stops_ok

    # Arm
    with js_lock:
        arm_move_count = max(arm_episode_count, sum(1 for s in arm_segments if s["state"] == "moving"))
        net_delta = arm_net_delta
        joint_net = dict(arm_joint_net)
    arm_changed_ok = net_delta >= ARM_TOTAL_DELTA_TOL
    arm_ok = arm_changed_ok and arm_move_count >= 1

    # Disposal
    with event_lock:
        disp_ok = disposal_correct_seen

    # Report
    print("Validation summary")
    print("  Base path: {}  total {:.3f} m, min {:.3f} m".format("OK" if base_path_ok else "FAIL", pl, MIN_PATH_METERS))
    print("  Stops pattern: {}  observed {} segments".format("OK" if two_stops_ok else "FAIL", len(segments)))
    print("  Arm: {}  net delta {:.4f} rad, tol {:.4f} rad, moves {}".format(
        "OK" if arm_ok else "FAIL", net_delta, ARM_TOTAL_DELTA_TOL, arm_move_count
    ))
    if joint_net:
        top = sorted(joint_net.items(), key=lambda kv: kv[1], reverse=True)[:3]
        pretty = ", ".join(f"{jn}:{v:.3f}" for jn, v in top)
        print(f"  Arm top joints by change: {pretty}")
    print("  Disposal event: {}  correct flag {}".format("OK" if disp_ok else "FAIL", "seen True" if disp_ok else "never True"))

    ok = base_ok and arm_ok and disp_ok
    print("APPROVED" if ok else "REJECTED")
    return 0 if ok else 2


# ---------------- main ----------------

def main():
    global BAG_PATH

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    if len(sys.argv) > 1:
        BAG_PATH = sys.argv[1]
    if not BAG_PATH:
        print("Usage: python oracle_ros1_bag_validator.py <path_to_bag> or set BAG_PATH")
        sys.exit(1)

    rospy.init_node("oracle_ros1_bag_validator", anonymous=True)
    rospy.set_param("/use_sim_time", True)

    # Wait briefly for ROS master
    try:
        import rosgraph
        t0 = time.time()
        while not rosgraph.is_master_online() and time.time() - t0 < 10.0:
            time.sleep(0.2)
        if not rosgraph.is_master_online():
            rospy.logwarn("ROS master not detected, rosbag may exit immediately")
    except Exception:
        pass

    # Base movement topic
    rospy.Subscriber("/odom_mocap", Odometry, odom_cb, queue_size=100)

    # Arm joint state topic
    rospy.Subscriber(JOINT_TOPIC, JointState, joint_cb, queue_size=50)

    # Disposal event topic
    rospy.Subscriber(DISPOSAL_TOPIC, String, disposal_cb, queue_size=10)

    # Start playback
    start_bag_play(BAG_PATH)

    # Wait for bag to finish
    try:
        while not rospy.is_shutdown():
            if _bag_proc is not None and _bag_proc.poll() is not None:
                break
            time.sleep(0.25)
    finally:
        stop_bag()

    code = validate()
    sys.exit(code)


if __name__ == "__main__":
    main()