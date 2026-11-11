#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash
# ros2 launch puts /ros2_ws/install first; keep the shared oracle logic importable
export PYTHONPATH=/workspace:${PYTHONPATH}
echo "rodeo-oracle (ROS 2): ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0} legacy_proofs=${LEGACY_PROOFS:-1}"
exec "$@"
