# RODEO oracle, ROS 2 (default). The oracle and its validator nodes run as ROS 2
# nodes; validators serve rodeo_interfaces/srv/ValidateProof and can be written
# in any language. Build context: repo root. (Pure-Python alternative:
# Dockerfile.python, compose profile "python".)
FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-humble-rosbag2-py ros-humble-rosbag2-storage-mcap \
      python3-pip python3-yaml python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Chain access (same set as the bridge) and rosbags for legacy ROS 1 bags.
# numpy stays < 2: ROS 2 Humble's message modules are built against numpy 1.
RUN pip3 install --no-cache-dir web3==6.11.4 websockets==13.1 rosbags==0.11.9 "numpy<2" && \
    pip3 install --no-cache-dir --no-deps eth-account==0.13.7

WORKDIR /ros2_ws
COPY robot-agent/ros2_ws/src/rodeo_interfaces ./src/rodeo_interfaces
COPY robot-agent/ros2_ws/src/rodeo_common ./src/rodeo_common
COPY oracle/ros2_ws/src/rodeo_oracle ./src/rodeo_oracle
RUN source /opt/ros/humble/setup.bash && colcon build && rm -rf build log

# Shared oracle logic (chain client, checks, validator rules), also used by the
# pure-Python oracle
WORKDIR /workspace
COPY oracle/oracle_node/ /workspace/oracle_node/
COPY oracle/addresses.json /workspace/addresses.json
RUN mkdir -p /workspace/abi /workspace/state
ENV PYTHONPATH=/workspace

COPY oracle/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN echo 'source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash' >> /root/.bashrc
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "rodeo_oracle", "oracle.launch.py"]
