FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3-pip python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Same library versions as the ROS 1 bridge image. web3 6.11.4 pins
# hexbytes<0.4 while eth-account 0.13.7 asks for hexbytes>=1.2; the ROS 1 image
# ends up with hexbytes 0.3.1 and works. A modern pip refuses that combination,
# so eth-account is installed without its dependency check to reproduce it.
ARG WEB3_VERSION=6.11.4
ARG ETH_ACCOUNT_VERSION=0.13.7
ARG WEBSOCKETS_VERSION=13.1
RUN pip3 install --no-cache-dir web3==${WEB3_VERSION} websockets==${WEBSOCKETS_VERSION} && \
    pip3 install --no-cache-dir --no-deps eth-account==${ETH_ACCOUNT_VERSION}

WORKDIR /ros2_ws
COPY ros2_ws/src ./src
RUN source /opt/ros/humble/setup.bash && colcon build && rm -rf build log

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN echo 'source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash' >> /root/.bashrc

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bridge"]
