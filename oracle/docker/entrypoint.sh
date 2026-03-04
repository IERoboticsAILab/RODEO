#!/bin/bash
set -e

# Source ROS setup
source /opt/ros/noetic/setup.bash

# Execute the command
exec "$@"
