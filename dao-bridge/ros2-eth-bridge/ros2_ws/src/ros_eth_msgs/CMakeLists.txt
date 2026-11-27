cmake_minimum_required(VERSION 3.8)
project(ros_eth_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(action_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/ServiceInfo.msg"
  "msg/TaskInfo.msg"
  "msg/TaskId.msg"
  "msg/ServiceId.msg"
  "msg/TaskAssignment.msg"
  "msg/TaskRegistered.msg"
  "msg/TaskRejection.msg"
  "msg/ServiceBusy.msg"
  "msg/TaskMeta.msg"
  "msg/ServiceMeta.msg"
  "msg/TxStatus.msg"
  "srv/GetService.srv"
  "srv/GetAllServices.srv"
  "srv/GetServicesByCreator.srv"
  "srv/GetTask.srv"
  "srv/GetAllTasks.srv"
  "srv/GetTasksByCreator.srv"
  "srv/GetTaskMeta.srv"
  "srv/GetServiceMeta.srv"
  "srv/GetBalance.srv"
  "srv/GetAllowance.srv"
  "action/RegisterService.action"
  "action/RegisterTask.action"
  "action/ActivateService.action"
  "action/RemoveService.action"
  "action/RemoveTask.action"
  "action/SubmitProof.action"
  "action/ActivateTask.action"
  "action/SetServiceBusy.action"
  "action/TransferToken.action"
  "action/ApproveSpender.action"
  DEPENDENCIES action_msgs
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
