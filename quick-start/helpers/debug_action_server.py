#!/usr/bin/env python3
"""
Debug script to check action server status
"""
import rospy
import actionlib
from ros_eth_msgs.msg import RegisterServiceAction

def check_action_server():
    rospy.init_node('debug_action_server', anonymous=True)
    
    print("=" * 60)
    print("Debugging ROS Action Server Status")
    print("=" * 60)
    
    client = actionlib.SimpleActionClient('/dao/register_service_action', RegisterServiceAction)
    
    print("\n1. Checking if action server exists...")
    if client.wait_for_server(timeout=rospy.Duration(5)):
        print("✅ Action server is reachable")
    else:
        print("❌ Action server not found")
        return
    
    print("\n2. Checking action server state...")
    state = client.get_state()
    state_names = {
        0: "PENDING",
        1: "ACTIVE", 
        2: "PREEMPTED",
        3: "SUCCEEDED",
        4: "ABORTED",
        5: "REJECTED",
        6: "PREEMPTING",
        7: "RECALLING",
        8: "RECALLED",
        9: "LOST"
    }
    print(f"   Current state: {state_names.get(state, 'UNKNOWN')} ({state})")
    
    print("\n3. Checking for active goals...")
    # Try to cancel any existing goals
    client.cancel_all_goals()
    print("   Sent cancel_all_goals()")
    rospy.sleep(1)
    
    print("\n4. Checking topics...")
    import subprocess
    result = subprocess.run(['rostopic', 'list'], capture_output=True, text=True)
    topics = [t for t in result.stdout.split('\n') if 'register_service' in t]
    for topic in topics:
        print(f"   {topic}")
    
    print("\n5. Checking for stuck goals...")
    result = subprocess.run(['rostopic', 'echo', '/dao/register_service_action/status', '-n', '1'], 
                          capture_output=True, text=True, timeout=3)
    if result.stdout:
        print("   Status messages:")
        print(result.stdout[:500])
    
    print("\n" + "=" * 60)
    print("Debug complete. Try running robot emulator again.")
    print("=" * 60)

if __name__ == '__main__':
    try:
        check_action_server()
    except Exception as e:
        print(f"Error: {e}")
