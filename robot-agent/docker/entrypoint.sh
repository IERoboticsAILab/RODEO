#!/bin/bash
# The agent runs as the container's main process (not through ros2 launch), so
# `docker stop` reaches it directly and it can deactivate its services first.
set -e
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash

BIN=/ros2_ws/install/rodeo_agent/lib/rodeo_agent
SERVICES=${RODEO_SERVICES_FILE:-/config/services.yaml}
ROS_ARGS=(--ros-args)
[ -n "${ROBOT_NAMESPACE:-}" ] && ROS_ARGS+=(-r __ns:=/${ROBOT_NAMESPACE})

case "${1:-agent}" in
  agent)
    echo "rodeo-agent: ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0} namespace='${ROBOT_NAMESPACE:-}' services=${SERVICES}"
    exec "$BIN/agent" "${ROS_ARGS[@]}" -p services_file:="$SERVICES" \
         -p proof_dir:="${PROOF_DIR:-/root/oracle/proofs}" ;;
  fake-executor)
    echo "fake-executor: ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0} namespace='${ROBOT_NAMESPACE:-}' proof_mode=${PROOF_MODE:-rodeo}"
    exec "$BIN/fake_executor" "${ROS_ARGS[@]}" -p services_file:="$SERVICES" \
         -p proof_mode:="${PROOF_MODE:-rodeo}" ;;
  *)
    exec "$@" ;;
esac
