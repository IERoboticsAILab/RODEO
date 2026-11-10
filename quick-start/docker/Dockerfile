FROM ros:humble-ros-base
SHELL ["/bin/bash", "-c"]
ENV PYTHONUNBUFFERED=1

# Build only the message package (build context is the repo root)
WORKDIR /ros2_ws
COPY dao-bridge/ros2-eth-bridge/ros2_ws/src/ros_eth_msgs ./src/ros_eth_msgs
RUN source /opt/ros/humble/setup.bash && colcon build && rm -rf build log

WORKDIR /root/robot_emulator_ws
COPY quick-start/robot_emulator_demo.py ./robot_emulator_demo.py
COPY quick-start/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x ./robot_emulator_demo.py /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["emulator"]
