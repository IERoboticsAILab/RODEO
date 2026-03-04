#!/usr/bin/env python3

import rospy
import actionlib
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from actionlib_msgs.msg import GoalStatus

class NavigationEngine:
    def __init__(self, action_name='/move_base'):
        self._action_name = action_name
        
        # Best Practice: Ensure we don't start before simulation time is active
        while not rospy.is_shutdown() and rospy.get_time() == 0:
            rospy.logwarn_once(f"[{self.__class__.__name__}] Waiting for clock...")
            rospy.sleep(0.1)

        self._client = actionlib.SimpleActionClient(self._action_name, MoveBaseAction)
        
        rospy.loginfo(f"[{self.__class__.__name__}] Connecting to {self._action_name}...")
        
        # We use a loop instead of a single timeout to handle simulation lag
        connected = False
        while not rospy.is_shutdown() and not connected:
            if self._client.wait_for_server(rospy.Duration(1.0)):
                connected = True
            else:
                rospy.loginfo(f"[{self.__class__.__name__}] Still waiting for {self._action_name}...")

        if not connected:
            raise RuntimeError(f"Could not connect to {self._action_name}")
            
        rospy.loginfo(f"[{self.__class__.__name__}] Connected successfully.")

    def move_to_pose(self, x, y, z, w):
        goal = MoveBaseGoal()
        goal.target_pose.header.frame_id = "map"
        goal.target_pose.header.stamp = rospy.Time.now()
        goal.target_pose.pose.position.x = x
        goal.target_pose.pose.position.y = y
        goal.target_pose.pose.orientation.z = z
        goal.target_pose.pose.orientation.w = w

        self._client.send_goal(goal)
        self._client.wait_for_result()
        return self._client.get_state() == GoalStatus.SUCCEEDED