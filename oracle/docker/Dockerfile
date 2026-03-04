FROM osrf/ros:noetic-desktop-full

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=noetic

# Install Python dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-rospy \
    python3-rosbag \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python packages
COPY oracle/docker/requirements.txt /tmp/requirements.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Create workspace
WORKDIR /workspace

# Copy oracle code
COPY oracle/oracle_node/ /workspace/oracle_node/
COPY oracle/addresses.json /workspace/addresses.json

# Copy ABI files from build context
# These will be mapped or copied during build
RUN mkdir -p /workspace/abi

# Source ROS setup in bashrc for interactive shells
RUN echo "source /opt/ros/noetic/setup.bash" >> /root/.bashrc

# Set environment variables for the oracle
ENV ROS_SETUP=/opt/ros/noetic/setup.bash
ENV ROS_DISTRO=noetic
ENV PYTHONPATH=/workspace:${PYTHONPATH}

# Create entrypoint script
COPY oracle/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-m", "oracle_node.main"]
