#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash

if [ "${1:-emulator}" = "emulator" ]; then
    shift || true
    ARGS=("$@")
    [ "${SKIP_REGISTRATION:-false}" = "true" ] && ARGS+=(--skip-registration)
    [ -n "${ROBOT_NAMESPACE:-}" ] && ARGS+=(--ros-args -r __ns:=/${ROBOT_NAMESPACE})
    exec python3 /root/robot_emulator_ws/robot_emulator_demo.py "${ARGS[@]}"
fi
exec "$@"
