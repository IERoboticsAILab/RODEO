#!/bin/bash
set -e

# Source ROS setup
source /opt/ros/noetic/setup.bash

# Source catkin workspace with ros_eth_msgs
source /root/catkin_ws/devel/setup.bash

# Execute the command
exec "$@"
