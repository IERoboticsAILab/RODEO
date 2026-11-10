#!/bin/bash
set -e

# Source ROS setup
source /opt/ros/noetic/setup.bash

# The validator replays proof bags with `rosbag play`, which needs a ROS 1
# master. The ROS 1 bridge used to provide one as a side effect of roslaunch;
# with the ROS 2 bridge there is none, so start our own if none is running.
master_online() {
    python3 -c "import rosgraph, sys; sys.exit(0 if rosgraph.is_master_online() else 1)" 2>/dev/null
}
if ! master_online; then
    roscore > /tmp/roscore.log 2>&1 &
    for _ in $(seq 1 40); do master_online && break; sleep 0.5; done
    master_online && echo "Started ROS 1 master for rosbag replay" \
                  || echo "WARNING: could not start a ROS 1 master (see /tmp/roscore.log)"
fi

# Execute the command
exec "$@"
