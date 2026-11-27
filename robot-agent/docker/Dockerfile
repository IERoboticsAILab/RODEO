# RODEO robot agent (also contains the fake executor). Build context: repo root.
FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1
SHELL ["/bin/bash", "-c"]

# rosbag2 with MCAP storage for proof bags
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-humble-rosbag2-py ros-humble-rosbag2-storage-mcap \
      ros-humble-rmw-cyclonedds-cpp \
      python3-yaml python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws
COPY dao-bridge/ros2-eth-bridge/ros2_ws/src/ros_eth_msgs ./src/ros_eth_msgs
COPY robot-agent/ros2_ws/src ./src
RUN source /opt/ros/humble/setup.bash && colcon build && rm -rf build log

COPY robot-agent/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN echo 'source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash' >> /root/.bashrc

ENTRYPOINT ["/entrypoint.sh"]
CMD ["agent"]
