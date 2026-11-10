# RODEO oracle v2: plain Python. Proofs are read with `rosbags`, so neither ROS 1
# nor ROS 2 is installed. Build context: repo root.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY oracle/docker/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && \
    pip install --no-deps eth-account==0.13.7 && \
    pip install "setuptools<70"            # web3 6.x imports pkg_resources

# Shared RODEO conventions (task descriptions, service schema, proof URIs)
COPY robot-agent/ros2_ws/src/rodeo_common /tmp/rodeo_common
RUN pip install --no-deps /tmp/rodeo_common && rm -rf /tmp/rodeo_common

WORKDIR /workspace
COPY oracle/oracle_node/ /workspace/oracle_node/
COPY oracle/addresses.json /workspace/addresses.json
RUN mkdir -p /workspace/abi /workspace/state

ENV PYTHONPATH=/workspace
CMD ["python3", "-m", "oracle_node.main"]
