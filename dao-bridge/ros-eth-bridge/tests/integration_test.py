#!/usr/bin/env python3
import sys
import time
import threading
import rospy
import actionlib
from ros_eth_msgs.srv import (
    GetAllServices, GetAllServicesRequest,
    GetAllTasks, GetAllTasksRequest,
    GetServicesByCreator, GetServicesByCreatorRequest,
    GetTasksByCreator, GetTasksByCreatorRequest,
    GetService, GetServiceRequest,
    GetTask, GetTaskRequest,
    GetBalance, GetBalanceRequest,
    GetAllowance, GetAllowanceRequest,
)
from ros_eth_msgs.msg import (
    TransferTokenAction, TransferTokenGoal, TransferTokenResult,
    ApproveSpenderAction, ApproveSpenderGoal, ApproveSpenderResult,
    RegisterServiceAction, RegisterServiceGoal, RegisterServiceResult,
    RegisterTaskAction, RegisterTaskGoal, RegisterTaskResult,
    SetServiceBusyAction, SetServiceBusyGoal, SetServiceBusyResult,
    RemoveServiceAction, RemoveServiceGoal, RemoveServiceResult,
    RemoveTaskAction, RemoveTaskGoal, RemoveTaskResult,
    ServiceBusy, ServiceMeta, TaskRegistered,
)

RESULT_TIMEOUT = 120  # seconds

def wait_for_topic(msg_type, topic, timeout=15.0):
    msg = rospy.wait_for_message(topic, msg_type, timeout=timeout)
    return msg

def wait_action(client, goal):
    client.send_goal(goal)
    if not client.wait_for_result(rospy.Duration(RESULT_TIMEOUT)):
        raise RuntimeError(f"Action {client.action_client.ns} timed out")
    res = client.get_result()
    if not res.ok:
        raise RuntimeError(f"Action {client.action_client.ns} failed: {res}")
    return res

def main():
    rospy.init_node("ros_eth_bridge_integration_test", anonymous=True)

    # ----- Service proxies -----
    srv_get_all_services = rospy.ServiceProxy("/dao/get_all_services", GetAllServices)
    srv_get_all_tasks    = rospy.ServiceProxy("/dao/get_all_tasks", GetAllTasks)
    srv_get_services_by  = rospy.ServiceProxy("/dao/get_services_by_creator", GetServicesByCreator)
    srv_get_tasks_by     = rospy.ServiceProxy("/dao/get_tasks_by_creator", GetTasksByCreator)
    srv_get_service      = rospy.ServiceProxy("/dao/get_service_by_id", GetService)
    srv_get_task         = rospy.ServiceProxy("/dao/get_task_by_id", GetTask)
    srv_get_balance      = rospy.ServiceProxy("/dao/get_balance", GetBalance)
    srv_get_allowance    = rospy.ServiceProxy("/dao/get_allowance", GetAllowance)

    # ----- Action clients -----
    ac_transfer   = actionlib.SimpleActionClient("/dao/transfer_token_action", TransferTokenAction)
    ac_approve    = actionlib.SimpleActionClient("/dao/approve_spender_action", ApproveSpenderAction)
    ac_reg_srv    = actionlib.SimpleActionClient("/dao/register_service_action", RegisterServiceAction)
    ac_reg_task   = actionlib.SimpleActionClient("/dao/register_task_action",   RegisterTaskAction)
    ac_set_busy   = actionlib.SimpleActionClient("/dao/set_service_busy_action", SetServiceBusyAction)
    ac_rm_srv     = actionlib.SimpleActionClient("/dao/remove_service_action", RemoveServiceAction)
    ac_rm_task    = actionlib.SimpleActionClient("/dao/remove_task_action", RemoveTaskAction)

    rospy.loginfo("Waiting for services/actions...")
    for proxy in [
        srv_get_all_services, srv_get_all_tasks, srv_get_services_by, srv_get_tasks_by,
        srv_get_service, srv_get_task, srv_get_balance, srv_get_allowance
    ]:
        proxy.wait_for_service(timeout=30)

    for ac in [ac_transfer, ac_approve, ac_reg_srv, ac_reg_task, ac_set_busy, ac_rm_srv, ac_rm_task]:
        ac.wait_for_server(rospy.Duration(30))

    # ----- Config you should set before running -----
    wallet_addr = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
    spender_addr = "0x712516e61C8B383dF4A63CFe83d7701Bce54B03e"  # task_manager address
    transfer_to  = "0xdF3e18d64BC6A983f673Ab319CCaE4f1a57C7097"
    assert wallet_addr and spender_addr, "Set ~wallet_addr and ~spender_addr ROS params for the test"

    # 1) Baseline reads
    rospy.loginfo("Baseline get_all_*")
    assert srv_get_all_services(GetAllServicesRequest()).ok
    assert srv_get_all_tasks(GetAllTasksRequest()).ok

    # 2) Balance and allowance
    bal = srv_get_balance(GetBalanceRequest(owner=wallet_addr))
    rospy.loginfo(f"Balance {bal.balance_wei}")
    allo = srv_get_allowance(GetAllowanceRequest(owner=wallet_addr, spender=spender_addr))
    rospy.loginfo(f"Allowance {allo.allowance_wei}")

    # 3) Approve
    #rospy.loginfo("Approve spender...")
    #wait_action(ac_approve, ApproveSpenderGoal(spender=spender_addr, amount="5", min_confirmations=1))

    # 4) Transfer (self-transfer by default)
    #rospy.loginfo("Transfer token...")
    #wait_action(ac_transfer, TransferTokenGoal(to=transfer_to, amount="1", min_confirmations=1))

    # 5) Register service
    rospy.loginfo("Register service...")
    srv_res = wait_action(ac_reg_srv, RegisterServiceGoal(
        name="TestService",
        description="Integration test",
        category="Logistics",
        service_type="Transport",
        price="1",
        provider_type=0,
        min_confirmations=1,
    ))
    service_id = 1  # assuming first; fetch if needed
    # Confirm via service call
    gsr = srv_get_all_services(GetAllServicesRequest())
    assert gsr.ok and len(gsr.services) >= 1

    # 6) Register task
    rospy.loginfo("Register task...")
    task_res = wait_action(ac_reg_task, RegisterTaskGoal(
        description="Test Task",
        category="Logistics",
        task_type="Pickup",
        reward="1",
        min_confirmations=1,
    ))
    task_id = 1  # assuming first
    gtr = srv_get_all_tasks(GetAllTasksRequest())
    assert gtr.ok and len(gtr.tasks) >= 1

    # 7) Event listener check (service_registered and task_registered)
    try:
        srv_meta_evt = wait_for_topic(ServiceMeta, "/dao/service_registered", timeout=10.0)
        rospy.loginfo(f"Service registered event: {srv_meta_evt.id}")
    except Exception as e:
        rospy.logwarn(f"No service_registered event observed: {e}")
    try:
        task_reg_evt = wait_for_topic(TaskRegistered, "/dao/task_registered", timeout=10.0)
        rospy.loginfo(f"Task registered event: {task_reg_evt.task_id}")
    except Exception as e:
        rospy.logwarn(f"No task_registered event observed: {e}")

    # 8) Set busy
    rospy.loginfo("Set service busy...")
    wait_action(ac_set_busy, SetServiceBusyGoal(service_id=service_id, is_busy=True, min_confirmations=1))
    # Wait for event
    try:
        busy_evt = wait_for_topic(ServiceBusy, "/dao/service_busy", timeout=10.0)
        rospy.loginfo(f"Service busy event: {busy_evt.service_id}, busy={busy_evt.busy}")
    except Exception as e:
        rospy.logwarn(f"No service_busy event observed: {e}")

    # 9) Remove service/task
    rospy.loginfo("Remove service...")
    wait_action(ac_rm_srv, RemoveServiceGoal(service_id=service_id, min_confirmations=1))
    rospy.loginfo("Remove task...")
    wait_action(ac_rm_task, RemoveTaskGoal(task_id=task_id, min_confirmations=1))

    rospy.loginfo("Integration smoke test finished OK")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        rospy.logerr(f"Test failed: {exc}")
        sys.exit(1)
