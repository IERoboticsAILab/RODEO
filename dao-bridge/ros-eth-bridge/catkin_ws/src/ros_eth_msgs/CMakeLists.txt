cmake_minimum_required(VERSION 3.0.2)
project(ros_eth_msgs)

find_package(catkin REQUIRED COMPONENTS
  std_msgs
  message_generation
  actionlib_msgs
)

add_message_files(
  FILES
    ServiceInfo.msg
    TaskInfo.msg
    TaskId.msg
    ServiceId.msg
    TaskAssignment.msg
    TaskRegistered.msg
    TaskRejection.msg
    ServiceBusy.msg
    TaskMeta.msg
    ServiceMeta.msg
    TxStatus.msg
)

add_service_files(
  FILES
    GetService.srv
    GetAllServices.srv
    GetServicesByCreator.srv
    GetTask.srv
    GetAllTasks.srv
    GetTasksByCreator.srv
    GetTaskMeta.srv
    GetServiceMeta.srv
    GetBalance.srv
    GetAllowance.srv
)

add_action_files(
  DIRECTORY action
  FILES
    RegisterService.action
    RegisterTask.action
    ActivateService.action
    RemoveService.action
    RemoveTask.action
    SubmitProof.action
    ActivateTask.action
    SetServiceBusy.action
    TransferToken.action
    ApproveSpender.action
)

generate_messages(
  DEPENDENCIES
    std_msgs
    actionlib_msgs
)

catkin_package(
  CATKIN_DEPENDS message_runtime std_msgs actionlib_msgs
)
