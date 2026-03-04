FROM ros:noetic-ros-base-focal

# Use bash for RUN commands to support 'source'
SHELL ["/bin/bash", "-c"]

# Install Python dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-rospy \
    python3-actionlib \
    python3-catkin-pkg-modules \
    python3-rosdep \
    ros-noetic-actionlib \
    ros-noetic-actionlib-msgs \
    ros-noetic-message-generation \
    ros-noetic-message-runtime \
    && rm -rf /var/lib/apt/lists/*

# Build catkin workspace with ros_eth_msgs
# Build context is repo root
WORKDIR /root/catkin_ws
COPY dao-bridge/ros-eth-bridge/catkin_ws/src /root/catkin_ws/src
RUN source /opt/ros/noetic/setup.bash && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y && \
    catkin_make

# Create robot emulator workspace
WORKDIR /root/robot_emulator_ws

# Copy robot emulator script (context is repo root)
COPY quick-start/robot_emulator_demo.py /root/robot_emulator_ws/robot_emulator_demo.py
RUN chmod +x /root/robot_emulator_ws/robot_emulator_demo.py

# Setup ROS environment
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc

# Set entrypoint (context is repo root)
COPY quick-start/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "/root/robot_emulator_ws/robot_emulator_demo.py"]

# To skip registration on subsequent runs:
# docker run <image> python3 /root/robot_emulator_ws/robot_emulator_demo.py --skip-registration
