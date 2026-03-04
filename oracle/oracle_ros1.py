# oracle_ros1_docker.py
import os
import sys
import time
import math
import signal
import subprocess
from threading import Lock

import rospy
from nav_msgs.msg import Odometry
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory

# -------------- user config --------------
BAG_PATH = os.environ.get("BAG_PATH", "/path/to/my_run.bag")

# Put your docker run here, or set GAZEBO_LAUNCH in the environment
GAZEBO_LAUNCH = os.environ.get(
    "GAZEBO_LAUNCH",
    # example: will be ignored unless you overwrite it
    "echo 'Set GAZEBO_LAUNCH to your docker run command'"
)

PLAY_RATE = float(os.environ.get("PLAY_RATE", "2.0"))

ODOM_TOPIC = os.environ.get("ODOM_TOPIC", "/odom")
JOINT_STATES_TOPIC = os.environ.get("JOINT_STATES_TOPIC", "/joint_states")
JOINT_TRAJ_CMD_TOPIC = os.environ.get("JOINT_TRAJ_CMD_TOPIC", "/arm_controller/joint_trajectory")
BASE_CMD_TOPIC = os.environ.get("BASE_CMD_TOPIC", "/diff_drive_controller/cmd_vel")

MIN_PATH_METERS = float(os.environ.get("MIN_PATH_METERS", "0.5"))
JOINT_POS_TOL = float(os.environ.get("JOINT_POS_TOL", "0.03"))
SETTLE_SEC = float(os.environ.get("SETTLE_SEC", "2.0"))
# -------------- end config --------------

_gazebo_proc = None
_bag_proc = None
_shutdown = False

odom_lock = Lock()
last_odom = None
path_len = 0.0

js_lock = Lock()
last_joint_states = None

traj_lock = Lock()
last_cmd_goal = None

def launch_gazebo():
    """
    Starts Gazebo using the exact shell string in GAZEBO_LAUNCH.
    Works with docker run, including env expansion and quotes.
    """
    global _gazebo_proc
    _gazebo_proc = subprocess.Popen(
        GAZEBO_LAUNCH,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        preexec_fn=os.setsid,  # own process group for clean kill
        executable="/bin/bash",
    )
    rospy.loginfo("Launched Gazebo command")
    # give it a moment to bring up roscore and gazebo
    time.sleep(5.0)

def unpause_gazebo():
    try:
        rospy.wait_for_service("/gazebo/unpause_physics", timeout=30.0)
        import std_srvs.srv as srvs
        unpause = rospy.ServiceProxy("/gazebo/unpause_physics", srvs.Empty)
        unpause()
        rospy.loginfo("Unpaused Gazebo physics")
    except Exception as e:
        rospy.logwarn("Could not unpause Gazebo: %s", e)

def start_bag_play():
    """
    Plays the bag at the chosen rate.
    Excludes TF and heavy sensors to avoid conflicts with the sim.
    """
    global _bag_proc
    cmd = [
        "rosbag", "play", BAG_PATH,
        "-r", str(PLAY_RATE),
        "-x", r"/tf($|/.*)|/tf_static|/camera/.*|/lidar/.*|/joint_states"
    ]
    _bag_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
    )
    rospy.loginfo("Started rosbag play at rate %.2f", PLAY_RATE)

def stop_processes():
    global _gazebo_proc, _bag_proc
    for p in [_bag_proc, _gazebo_proc]:
        if p is None:
            continue
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            pass
    time.sleep(1.0)
    for p in [_bag_proc, _gazebo_proc]:
        if p is None:
            continue
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass

def sig_handler(sig, frame):
    stop_processes()
    rospy.signal_shutdown("signal")

def odom_cb(msg: Odometry):
    global last_odom, path_len
    with odom_lock:
        if last_odom is not None:
            dx = msg.pose.pose.position.x - last_odom.pose.pose.position.x
            dy = msg.pose.pose.position.y - last_odom.pose.pose.position.y
            path_len += math.hypot(dx, dy)
        last_odom = msg

def js_cb(msg: JointState):
    global last_joint_states
    with js_lock:
        last_joint_states = msg

def traj_cb(msg: JointTrajectory):
    if not msg.joint_names or not msg.points:
        return
    final = msg.points[-1].positions
    with traj_lock:
        global last_cmd_goal
        last_cmd_goal = {name: pos for name, pos in zip(msg.joint_names, final)}

def validate():
    rospy.sleep(SETTLE_SEC)
    # arm check
    joint_ok = True
    joint_report = "no trajectory command observed"
    with traj_lock:
        goal = dict(last_cmd_goal) if last_cmd_goal is not None else None
    with js_lock:
        js = last_joint_states
    if goal and js:
        now_map = {n: p for n, p in zip(js.name, js.position)}
        errors = {}
        for jn, tgt in goal.items():
            if jn in now_map:
                errors[jn] = abs(now_map[jn] - tgt)
        if errors:
            max_err = max(errors.values())
            joint_ok = max_err <= JOINT_POS_TOL
            joint_report = f"max joint error {max_err:.4f} rad, tol {JOINT_POS_TOL:.4f} rad"
        else:
            joint_ok = False
            joint_report = "could not match commanded joints to joint states"
    # base check
    with odom_lock:
        pl = path_len
    base_ok = pl >= MIN_PATH_METERS
    base_report = f"path length {pl:.3f} m, min {MIN_PATH_METERS:.3f} m"
    ok = joint_ok and base_ok
    print("Validation summary")
    print(f"  Base: {'OK' if base_ok else 'FAIL'}  {base_report}")
    print(f"  Arm:  {'OK' if joint_ok else 'FAIL'}  {joint_report}")
    print("APPROVED" if ok else "REJECTED")
    return 0 if ok else 2

def main():
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # Make sure this process uses the same master as the container
    # If you run the container with --network host you can often leave this as default
    # Otherwise set ROS_MASTER_URI and ROS_IP in your shell before running
    rospy.init_node("oracle_ros1", anonymous=True)
    rospy.set_param("/use_sim_time", True)

    rospy.Subscriber(ODOM_TOPIC, Odometry, odom_cb, queue_size=50)
    rospy.Subscriber(JOINT_STATES_TOPIC, JointState, js_cb, queue_size=50)
    rospy.Subscriber(JOINT_TRAJ_CMD_TOPIC, JointTrajectory, traj_cb, queue_size=10)

    launch_gazebo()
    unpause_gazebo()
    time.sleep(1.0)
    
    '''
    start_bag_play()

    # wait for bag to finish
    while not rospy.is_shutdown():
        if _bag_proc is not None and _bag_proc.poll() is not None:
            break
        time.sleep(0.5)

    code = validate()
    stop_processes()
    sys.exit(code)
    '''

if __name__ == "__main__":
    main()
