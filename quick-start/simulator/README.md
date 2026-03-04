sudo apt update
sudo apt install -y \
  ros-noetic-navigation \
  ros-noetic-stage-ros \
  ros-noetic-map-server \
  ros-noetic-amcl \
  ros-noetic-rviz \
  python3-catkin-tools \
  git


mkdir -p ~/catkin_ws/src
cd ~/catkin_ws
catkin init



cd ~/catkin_ws/src
git clone -b indigo-devel https://github.com/ros-planning/navigation_tutorials.git


cd ~/catkin_ws
rosdep update
rosdep install --from-paths src --ignore-src -r -y
catkin build



source ~/catkin_ws/devel/setup.bash


roslaunch navigation_stage move_base_amcl_2.5cm.launch --screen
