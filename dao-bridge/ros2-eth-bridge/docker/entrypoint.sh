#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash

if [ "${1:-bridge}" = "bridge" ]; then
    ARGS=(config_file:=${ROS_ETH_DAO_YAML:-/config/dao.yaml}
          own_assignments_only:=${OWN_ASSIGNMENTS_ONLY:-true})
    [ -n "${ROBOT_NAMESPACE:-}" ] && ARGS+=(namespace:=${ROBOT_NAMESPACE})
    echo "ros2-eth-bridge: ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0} namespace='${ROBOT_NAMESPACE:-}'"
    exec ros2 launch ros_eth_bridge ros_eth_gateway.launch.py "${ARGS[@]}"
fi
exec "$@"
