"""Start one robot's RODEO agent (in the same namespace as its bridge).

    ros2 launch rodeo_agent agent.launch.py services_file:=/config/services.yaml namespace:=panther
    ros2 launch rodeo_agent agent.launch.py ... fake_executor:=true      # demo without a robot
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    ns = LaunchConfiguration("namespace")
    services = LaunchConfiguration("services_file")
    proofs = LaunchConfiguration("proof_dir")
    return LaunchDescription([
        DeclareLaunchArgument("namespace", default_value=""),
        DeclareLaunchArgument("services_file", description="the robot's services.yaml"),
        DeclareLaunchArgument("proof_dir", default_value="/root/oracle/proofs",
                              description="where executors write proofs; must be readable by the agent and the oracle"),
        DeclareLaunchArgument("fake_executor", default_value="false"),
        DeclareLaunchArgument("proof_mode", default_value="rodeo",
                              description="fake executor: rodeo | legacy"),
        Node(package="rodeo_agent", executable="agent", name="rodeo_agent", namespace=ns,
             output="screen", sigterm_timeout="30",
             parameters=[{"services_file": services, "proof_dir": proofs}]),
        Node(package="rodeo_agent", executable="fake_executor", name="fake_executor",
             namespace=ns, output="screen", condition=IfCondition(LaunchConfiguration("fake_executor")),
             parameters=[{"services_file": services,
                          "proof_mode": LaunchConfiguration("proof_mode")}]),
    ])
