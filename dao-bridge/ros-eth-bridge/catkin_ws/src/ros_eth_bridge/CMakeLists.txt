cmake_minimum_required(VERSION 3.0.2)
project(ros_eth_bridge)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  actionlib
  actionlib_msgs
  ros_eth_msgs
)

catkin_package()

catkin_install_python(PROGRAMS
  src/dao_listener_node.py
  src/dao_writer_node.py
  # legacy nodes kept for reference (not launched by default)
  scripts/show_balances.py
  scripts/set_allowance.py
  scripts/test_bridge.py
  scripts/robot_emulator.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch config
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
