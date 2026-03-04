#!/usr/bin/env python3
"""
Deep debug of ROS-ETH bridge action server
Tests transaction flow step by step
"""
import rospy
import actionlib
import sys
import time
from ros_eth_msgs.msg import RegisterServiceAction, RegisterServiceGoal

def test_action_server():
    rospy.init_node('deep_debug_action', anonymous=True)
    
    print("=" * 70)
    print("DEEP DEBUG: ROS-ETH Bridge Action Server")
    print("=" * 70)
    
    client = actionlib.SimpleActionClient('/dao/register_service_action', RegisterServiceAction)
    
    # Step 1: Check server availability
    print("\n[1/6] Checking action server availability...")
    if not client.wait_for_server(timeout=rospy.Duration(5)):
        print("❌ FAIL: Action server not reachable")
        return
    print("✅ PASS: Action server is reachable")
    
    # Step 2: Check current state
    print("\n[2/6] Checking action server state...")
    state = client.get_state()
    state_names = {0: "PENDING", 1: "ACTIVE", 2: "PREEMPTED", 3: "SUCCEEDED", 
                   4: "ABORTED", 5: "REJECTED", 6: "PREEMPTING", 7: "RECALLING",
                   8: "RECALLED", 9: "LOST"}
    print(f"   Current state: {state_names.get(state, 'UNKNOWN')} ({state})")
    
    if state == 9:
        print("⚠️  WARNING: Server in LOST state - canceling...")
        client.cancel_all_goals()
        time.sleep(2)
    
    # Step 3: Monitor status topic
    print("\n[3/6] Checking status topic...")
    try:
        import subprocess
        result = subprocess.run(
            ['rostopic', 'echo', '/dao/register_service_action/status', '-n', '1'],
            capture_output=True, text=True, timeout=2
        )
        if "status_list: []" in result.stdout:
            print("✅ PASS: No stuck goals in queue")
        else:
            print("⚠️  WARNING: Found status messages:")
            print(result.stdout[:300])
    except subprocess.TimeoutExpired:
        print("⚠️  WARNING: Status topic not responding")
    except Exception as e:
        print(f"⚠️  WARNING: Could not check status: {e}")
    
    # Step 4: Send a test goal with callback monitoring
    print("\n[4/6] Sending test goal with monitoring...")
    
    feedback_received = []
    result_received = [None]
    
    def feedback_cb(feedback):
        msg = f"   📊 Feedback: state={feedback.state}, confirmations={feedback.confirmations}"
        if feedback.tx_hash:
            msg += f", tx={feedback.tx_hash[:10]}..."
        if feedback.error:
            msg += f", error={feedback.error}"
        print(msg)
        feedback_received.append(feedback)
    
    def done_cb(state, result):
        print(f"   ✅ Done callback: state={state}, ok={result.ok}")
        result_received[0] = result
    
    goal = RegisterServiceGoal()
    goal.name = "Debug Test Service"
    goal.description = "Test service for debugging"
    goal.category = "Debug"
    goal.service_type = "Test"
    goal.price = "1"
    goal.provider_type = 0
    goal.min_confirmations = 1
    
    print("   Sending goal...")
    client.send_goal(goal, done_cb=done_cb, feedback_cb=feedback_cb)
    
    # Step 5: Wait with incremental timeout monitoring
    print("\n[5/6] Waiting for result (60s timeout with progress monitoring)...")
    start_time = time.time()
    check_interval = 5  # Check every 5 seconds
    
    while True:
        elapsed = time.time() - start_time
        
        if client.wait_for_result(timeout=rospy.Duration(check_interval)):
            # Goal completed
            print(f"   ✅ Goal completed after {elapsed:.1f}s")
            break
        
        # Timeout check
        if elapsed >= 60:
            print(f"   ❌ TIMEOUT after {elapsed:.1f}s")
            print(f"   Feedbacks received: {len(feedback_received)}")
            if feedback_received:
                last_fb = feedback_received[-1]
                print(f"   Last feedback: state={last_fb.state}, confirmations={last_fb.confirmations}")
            break
        
        # Progress update
        state = client.get_state()
        print(f"   ... {elapsed:.0f}s: state={state_names.get(state, 'UNKNOWN')}, feedbacks={len(feedback_received)}")
    
    # Step 6: Check result
    print("\n[6/6] Checking result...")
    result = client.get_result()
    final_state = client.get_state()
    
    if result:
        print(f"   Result: ok={result.ok}, tx={result.tx_hash[:16] if result.tx_hash else 'none'}...")
        print(f"   Block: {result.block_number}")
        print(f"   Final state: {state_names.get(final_state, 'UNKNOWN')}")
    else:
        print(f"   ❌ No result received")
        print(f"   Final state: {state_names.get(final_state, 'UNKNOWN')}")
    
    print("\n" + "=" * 70)
    print("ANALYSIS:")
    print("=" * 70)
    
    if len(feedback_received) == 0:
        print("❌ PROBLEM: No feedback received - action server not processing goal")
        print("   Likely causes:")
        print("   - Action server callback is blocked/crashed")
        print("   - Exception in execute_cb not being caught")
        print("   - Deadlock in nonce lock or Web3 connection")
    elif feedback_received[-1].state == "pending":
        print("❌ PROBLEM: Stuck at 'pending' state")
        print("   Likely causes:")
        print("   - Transaction not being broadcast to blockchain")
        print("   - Ganache not responding")
        print("   - Web3 connection issue")
    elif feedback_received[-1].state == "included":
        print("⚠️  PROBLEM: Stuck waiting for confirmations")
        print("   Likely causes:")
        print("   - Ganache not mining blocks")
        print("   - Confirmation count requirement too high")
    elif result and not result.ok:
        print("❌ PROBLEM: Transaction reverted")
        print("   Likely causes:")
        print("   - Smart contract rejected transaction (duplicate service?)")
        print("   - Insufficient gas")
        print("   - Contract logic requirement not met")
    elif result and result.ok:
        print("✅ SUCCESS: Everything worked correctly!")
    else:
        print("❌ PROBLEM: Unknown failure mode")
    
    print("\nNext steps:")
    if len(feedback_received) == 0:
        print("1. Check bridge logs: cd dao-bridge/ros-eth-bridge/docker && ./ros-bridge.sh logs")
        print("2. Look for Python exceptions or stack traces")
        print("3. Check if Web3 connection is alive")
    else:
        print("1. Check Ganache logs: cd blockchain-network/ganache-docker && ./ganache-docker.sh logs")
        print("2. Verify transactions are being mined")

if __name__ == '__main__':
    try:
        test_action_server()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
