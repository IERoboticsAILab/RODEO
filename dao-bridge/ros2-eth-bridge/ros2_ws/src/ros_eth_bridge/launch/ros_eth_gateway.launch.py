"""Start the RODEO bridge (dao_listener + dao_writer) for one wallet.

    ros2 launch ros_eth_bridge ros_eth_gateway.launch.py
    ros2 launch ros_eth_bridge ros_eth_gateway.launch.py namespace:=panther config_file:=/config/dao.yaml

Without a namespace the interfaces are /dao/... (same names as ROS 1).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    ns = LaunchConfiguration("namespace")
    cfg = LaunchConfiguration("config_file")
    own = LaunchConfiguration("own_assignments_only")
    return LaunchDescription([
        DeclareLaunchArgument("namespace", default_value="",
                              description="robot namespace, e.g. panther -> /panther/dao/..."),
        DeclareLaunchArgument("config_file", default_value="",
                              description="dao.yaml path; empty = $ROS_ETH_DAO_YAML or the packaged file"),
        DeclareLaunchArgument("own_assignments_only", default_value="true",
                              description="publish task_assigned only for this wallet"),
        Node(package="ros_eth_bridge", executable="dao_listener", name="dao_listener",
             namespace=ns, output="screen",
             parameters=[{"config_file": cfg, "poll_interval_sec": 1.0, "block_chunk": 1000,
                          "own_assignments_only": own}]),
        Node(package="ros_eth_bridge", executable="dao_writer", name="dao_writer",
             namespace=ns, output="screen",
             parameters=[{"config_file": cfg}]),
    ])
