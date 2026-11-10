from glob import glob

from setuptools import setup

package_name = "ros_eth_bridge"

setup(
    name=package_name,
    version="2.0.0",
    # `eth` is the ROS-free chain layer, copied unchanged from the ROS 1 bridge.
    packages=[package_name, "eth", "eth.dao", "eth.events"],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
        ("share/" + package_name + "/config", glob("config/*.yaml")),
        ("share/" + package_name + "/abi", glob("abi/*.json")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Tersoo Samuel Awai",
    maintainer_email="samuel.awai5@gmail.com",
    description="RODEO ROS 2 - Ethereum bridge",
    license="MIT",
    entry_points={
        "console_scripts": [
            "dao_listener = ros_eth_bridge.dao_listener_node:main",
            "dao_writer = ros_eth_bridge.dao_writer_node:main",
        ],
    },
)
