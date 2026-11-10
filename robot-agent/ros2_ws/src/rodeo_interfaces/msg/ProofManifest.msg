# First message in every proof bag, on /rodeo/manifest. It binds the bag to one
# task: the oracle rejects a proof whose manifest does not match the task.
uint32 FORMAT_VERSION=1

uint32 format_version
uint64 task_id
string executor          # wallet address of the robot that did the task
string robot             # robot name from services.yaml
string category
string task_type
string params_json       # the parameters the robot executed
builtin_interfaces/Time start
