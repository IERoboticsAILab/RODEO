FROM ros:noetic-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

SHELL ["/bin/bash", "-lc"]

# System packages for building and running
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-pip python3-dev \
    python3-rospkg python3-catkin-pkg-modules \
    python3-rosdep \
    ros-noetic-roslaunch \
    ros-noetic-std-msgs \
    ros-noetic-actionlib ros-noetic-actionlib-msgs \
    ros-noetic-message-generation ros-noetic-message-runtime \
    && rm -rf /var/lib/apt/lists/*

# Pin Python libraries to match the current host setup (web3 v5 path used in code)
ARG WEB3_VERSION=6.11.4
ARG ETH_ACCOUNT_VERSION=0.13.7
ARG PYYAML_VERSION=5.3.1
ARG WEBSOCKETS_VERSION=13.1
ARG REQUESTS_VERSION=2.32.4

RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir \
      web3==${WEB3_VERSION} \
      eth-account==${ETH_ACCOUNT_VERSION} \
      pyyaml==${PYYAML_VERSION} \
      requests==${REQUESTS_VERSION} \
      websockets==${WEBSOCKETS_VERSION}

# Prepare workspace
WORKDIR /root/catkin_ws
COPY catkin_ws/src /root/catkin_ws/src

# Install system deps for the ROS packages in src (ignores already-copied code)
RUN source /opt/ros/noetic/setup.bash && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y

# Build the workspace
RUN source /opt/ros/noetic/setup.bash && catkin_make

# Convenience: source the workspace on login
RUN echo 'source /opt/ros/noetic/setup.bash' >> /root/.bashrc && \
    echo 'source /root/catkin_ws/devel/setup.bash' >> /root/.bashrc

# Default command runs your launch file
CMD ["bash", "-lc", "source /opt/ros/noetic/setup.bash && source /root/catkin_ws/devel/setup.bash && roslaunch ros_eth_bridge ros_eth_gateway.launch"]
