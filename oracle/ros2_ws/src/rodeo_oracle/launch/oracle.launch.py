"""The RODEO oracle and its validator nodes, in the /oracle namespace.

    ros2 launch rodeo_oracle oracle.launch.py

Each validator serves rodeo_interfaces/srv/ValidateProof; the oracle's
`validators` parameter maps a service kind to it. To add one (in any language),
start its node here and add "Category/TaskType=validate/<name>".
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    ns = LaunchConfiguration("namespace")
    return LaunchDescription([
        DeclareLaunchArgument("namespace", default_value="oracle"),
        Node(package="rodeo_oracle", executable="delivery_validator", name="delivery_validator",
             namespace=ns, output="screen"),
        Node(package="rodeo_oracle", executable="charging_validator", name="charging_validator",
             namespace=ns, output="screen"),
        Node(package="rodeo_oracle", executable="oracle", name="oracle", namespace=ns, output="screen",
             parameters=[{"validators": ["Logistics/ItemTransport=validate/delivery",
                                         "Energy/Charging=validate/charging"]}]),
    ])
