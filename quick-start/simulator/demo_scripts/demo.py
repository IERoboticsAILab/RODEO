#!/usr/bin/env python3

import rospy
from navigation_move_base import NavigationEngine

class DemoMissionNode:
    """
    The main Application Node. 
    It manages the coordinates and decides where to go based on demo logic.
    """
    def __init__(self):
        # 1. Internal Database (Config)
        self.locations = {
            "bottom_right": {"x": -18.698, "y": -11.069, "z": -0.680, "w": 0.733},
            "start_room":   {"x": -13.045, "y": 4.102,  "z": 0.567, "w": 0.823},
            "front_start":  {"x": 2.303,   "y": 8.280,  "z": 0.022, "w": 0.999},
            "top_left":     {"x": 19.112,  "y": 18.273, "z": 0.663, "w": 0.748},
            "top_right":    {"x": 19.155,  "y": -16.322,"z": -0.978, "w": 0.205},
            "big_room":     {"x": 12.638,  "y": -6.038, "z": -0.999, "w": 0.003},
            "hallway":      {"x": -11.009, "y": -10.938,"z": -0.842, "w": 0.539}
        }

        # Initialize nav as None first
        self.nav = None

        # 2. Setup the Navigation Engine
        try:
            self.nav = NavigationEngine(action_name='/move_base')
        except RuntimeError as e:
            rospy.logerr(f"Shutdown: {e}")
            raise

    def run_task_delivery(self):
        """Logic for Delivery Task: Start Room -> bottom right Room -> Start Room"""
        rospy.loginfo("Starting task delivery...")
        self.execute_move("bottom_right")
        rospy.sleep(5) # Simulate pickup time
        self.execute_move("start_room")

    def run_task_battery_charging(self):
        """Logic for Battery Charging: go to top right room"""
        rospy.loginfo("Starting task battery charging...")
        self.execute_move("top_left")
        rospy.loginfo("Charging battery for 15 seconds...")
        rospy.sleep(15) # Simulate charging time
    
    def run_task_cleaning(self):
        """Logic for Cleaning task: clean all rooms..."""
        rospy.loginfo("Starting Cleaning task...")
        self.execute_move("front_start")
        self.execute_move("top_left")
        self.execute_move("top_right")
        self.execute_move("big_room")
        self.execute_move("hallway")
        self.execute_move("bottom_right")

    def execute_move(self, name):
        if self.nav is None:
            rospy.logerr("Cannot move: Navigation Engine not initialized.")
            return False

        """Helper to fetch data and call engine."""
        if name not in self.locations:
            rospy.logerr(f"Location {name} not found in database.")
            return False
        
        coords = self.locations[name]
        rospy.loginfo(f"Moving to: {name.upper()}")
        
        return self.nav.move_to_pose(coords['x'], coords['y'], coords['z'], coords['w'])

def main():
    rospy.init_node('demo_mission_node', anonymous=False)
    
    app = DemoMissionNode()

    # --- DEMO SELECTION LOGIC ---
    # Here is where you decide which scenario to run for your demo
    # For now, we will run Scenario A
    #app.run_task_delivery()
    #app.run_task_battery_charging() 
    app.run_task_cleaning()
    rospy.loginfo("Demo completed successfully.")
    #rospy.spin()

if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass