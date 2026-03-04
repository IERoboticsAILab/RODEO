import os
import sys
import time
import json
import math
import signal
import argparse
import subprocess
from threading import Lock

# ROS imports kept here to avoid loading ROS in the parent
import rospy
from std_msgs.msg import String
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState

# -------------- config --------------
PLAY_RATE = float(os.environ.get("PLAY_RATE", "3.0"))
MIN_STATE_SEC = float(os.environ.get("MIN_STATE_SEC", "0.5"))
POS_EPS = float(os.environ.get("POS_EPS", "0.002"))
ARM_POS_EPS = float(os.environ.get("ARM_POS_EPS", "0.005"))
ARM_TOTAL_DELTA_TOL = float(os.environ.get("ARM_TOTAL_DELTA_TOL", "0.05"))
MIN_ARM_STATE_SEC = float(os.environ.get("MIN_ARM_STATE_SEC", "0.0"))
MIN_PATH_METERS = float(os.environ.get("MIN_PATH_METERS", "0.10"))
JOINT_TOPIC = os.environ.get("JOINT_TOPIC", "/vx300s/joint_states")
DISPOSAL_TOPIC = "/disposal_event"
# -------------- end config --------------

_bag_proc = None

odom_lock = Lock()
last_pos = None
last_t = None
path_len = 0.0
segments = []
cur_state = None
cur_t0 = None

js_lock = Lock()
arm_last_map = None
arm_last_t = None
arm_init_map = None
arm_segments = []
arm_cur_state = None
arm_cur_t0 = None
arm_episode_count = 0
arm_net_delta = 0.0
arm_joint_net = {}

event_lock = Lock()
disposal_correct_seen = False
last_disposal = None

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

def _get_time(msg):
    try:
        t = msg.header.stamp.to_sec()
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
    global cur_state, cur_t0, segments
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
                    arm_joint_net[jn] = max(arm_joint_net.get(jn, 0.0), abs(pos - arm_init_map.get(jn, pos)))
            moving_now = max_step > ARM_POS_EPS
            _advance_arm_state(t, moving_now)
        elif arm_last_map is None:
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

def _finalize_all_segments():
    _finalize_segments("cur_state", "cur_t0", last_t, "segments", MIN_STATE_SEC)
    _finalize_segments("arm_cur_state", "arm_cur_t0", arm_last_t, "arm_segments", MIN_ARM_STATE_SEC)

def validate_and_report():
    _finalize_all_segments()

    with odom_lock:
        pl = path_len
    base_path_ok = pl >= MIN_PATH_METERS
    
    base_ok = base_path_ok

    with js_lock:
        arm_move_count = max(arm_episode_count, sum(1 for s in arm_segments if s["state"] == "moving"))
        net_delta = arm_net_delta
        joint_net = dict(arm_joint_net)
    arm_changed_ok = net_delta >= ARM_TOTAL_DELTA_TOL
    arm_ok = arm_changed_ok and arm_move_count >= 1

    with event_lock:
        disp_ok = disposal_correct_seen

    print("Validation summary")
    print("  Base path: {}  total {:.3f} m, min {:.3f} m".format("OK" if base_path_ok else "FAIL", pl, MIN_PATH_METERS))
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bag", required=True)
    args = parser.parse_args()

    signal.signal(signal.SIGINT, lambda s, f: rospy.signal_shutdown("signal"))
    signal.signal(signal.SIGTERM, lambda s, f: rospy.signal_shutdown("signal"))

    bag_path = args.bag
    if not bag_path:
        print("Bag path is required")
        sys.exit(3)

    rospy.init_node("oracle_ros1_bag_validator", anonymous=True)
    rospy.set_param("/use_sim_time", True)

    try:
        import rosgraph
        t0 = time.time()
        while not rosgraph.is_master_online() and time.time() - t0 < 10.0:
            time.sleep(0.2)
        if not rosgraph.is_master_online():
            rospy.logwarn("ROS master not detected, rosbag may exit immediately")
    except Exception:
        pass

    rospy.Subscriber("/odom_mocap", Odometry, odom_cb, queue_size=100)
    rospy.Subscriber(JOINT_TOPIC, JointState, joint_cb, queue_size=50)
    rospy.Subscriber(DISPOSAL_TOPIC, String, disposal_cb, queue_size=10)

    start_bag_play(bag_path)

    try:
        while not rospy.is_shutdown():
            if _bag_proc is not None and _bag_proc.poll() is not None:
                break
            time.sleep(0.25)
    finally:
        stop_bag()

    code = validate_and_report()
    sys.exit(code)

if __name__ == "__main__":
    main()
