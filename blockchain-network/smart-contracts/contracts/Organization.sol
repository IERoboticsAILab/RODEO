// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./IECoin.sol";

interface ITaskManager {
    function getTaskMeta(uint256 taskId) external view returns (uint256 tId, bytes32 categoryHash,  bytes32 serviceTypeHash, bool active, uint256 reward);
    function registerTask(string calldata description, string calldata category,  string calldata taskType, uint256 reward) external returns (uint256);
    function completeTask(uint256 taskId) external;
    function assignTaskExecutor(uint256 taskId, address executor, uint256 reward) external;
    function getTotalTasks() external view returns (uint256);
    function _unassignTask(uint256 taskId) external;
    function removeTask(uint256 taskId) external;
    function setOracle(address _oracle) external;
    function submitProof(uint256 taskId, string calldata proofURI) external;
    function activateTask(uint256 taskId) external;
}

interface IServiceManager {
    enum ProviderType { Robot, Human, Organization }
    function registerService(string calldata name, string calldata description, string calldata category, string calldata serviceType, uint256 price, ProviderType providerType ) external returns (uint256);
    function getServiceMeta(uint256 index) external view returns (uint256 sid, bytes32 categoryHash,  bytes32 serviceTypeHash, uint256 price, address creator, bool active, bool busy);
    function removeService(uint256 index) external;
    function getServiceCount() external view returns (uint256);
    function setBusy(uint256 index, bool isBusy) external;
    function activateService(uint256 index) external;
}

contract Organization is Ownable {
    IECoin public immutable token;
    ITaskManager public taskManager;
    IServiceManager public serviceManager;

    mapping(uint256 => uint256) public taskToService;
    mapping(uint256 => uint256) public serviceToTask;

    constructor(
        address tokenAddress
    ) Ownable(msg.sender) {
        token = IECoin(tokenAddress);
    }
    
    function deposit(uint256 amount) external {
        // pull IECoin from your EOA into this contract
        bool ok = token.transferFrom(msg.sender, address(this), amount);
        require(ok, "Deposit transfer failed");

        // allow TaskManager to pull up to `amount` from this contract
        ok = token.approve(address(taskManager), amount);
        require(ok, "Approve failed");

    }

    function setTaskManager(address _taskManager) external onlyOwner {
    taskManager = ITaskManager(_taskManager);
    }

    function setServiceManager(address _serviceManager) external onlyOwner {
        serviceManager = IServiceManager(_serviceManager);
    }

    function setOracle(address _oracle) external onlyOwner {
        taskManager.setOracle(_oracle);
    }

    // wrappers for TaskManager
    function registerTask(string calldata description, string calldata category,  string calldata taskType, uint256 reward) external onlyOwner returns (uint256) {
        uint256 taskId = taskManager.registerTask(description, category, taskType, reward);
        return taskId;
    }

    function removeTask(uint256 taskId) external onlyOwner {
        if (taskToService[taskId] != 0) {
            revert("Task assigned! Please unassing the task.");
        }
        taskManager.removeTask(taskId);
    }

     function activateTask(uint256 taskId) external onlyOwner {
        if (taskToService[taskId] != 0) {
            revert("Task assigned!");
        }
        taskManager.activateTask(taskId);
    }

    function unassignTask(uint256 taskId) external onlyOwner {
            _checkTaskCancelation(taskId);
    }

    function checkTaskCancelation(uint256 taskId) external {
        require(msg.sender == address(taskManager), "Only TaskManager");
        _checkTaskCancelation(taskId);
    }

    function _checkTaskCancelation(uint256 taskId) internal {
        uint256 svcId = taskToService[taskId];
        // make sure taskId is actually assigned to svcId
        if (serviceToTask[svcId] != taskId) {
            revert("Task not assigned, please remove task");
        }
        // notify TaskManager to unassign and refund
        taskManager._unassignTask(taskId);
        // mark the service as free again
        serviceManager.setBusy(svcId, false);
        // clear both mappings
        delete taskToService[taskId];
        delete serviceToTask[svcId];
        tryAssignTaskForService(svcId);

    }

    function completeTask( uint256 taskId) external onlyOwner {
        taskManager.completeTask(taskId);
    }

     function submitProofAsExecutor(uint256 taskId, string calldata proofURI) external onlyOwner {
        // lets the Organization contract act as service executor
        taskManager.submitProof(taskId, proofURI);
    }

        // wrappers for ServiceManager
    function registerService(string calldata name, string calldata description, string calldata category, string calldata serviceType, uint256 price, IServiceManager.ProviderType providerType) external onlyOwner returns (uint256) {
        uint256 serviceId = serviceManager.registerService(name, description, category, serviceType, price, providerType);
        return serviceId;
    }

    function activateService(uint256 serviceId) external onlyOwner {
        if (serviceToTask[serviceId] != 0) {
            revert("Service is already active!");
        }
        serviceManager.activateService(serviceId);
    }


    function removeService(uint256 serviceId) external onlyOwner {
        if (serviceToTask[serviceId] != 0) {
            revert("Service busy! Please unassing the task asociated to this service.");
        }
        serviceManager.removeService(serviceId);
    }

    function setServiceBusy(uint256 index, bool isBusy) external onlyOwner {
    serviceManager.setBusy(index, isBusy);
    }

        // Called by TaskManager after registering a task
    function onTaskRegistered(uint256 taskId) external {
        require(msg.sender == address(taskManager), "Unauthorized caller");
        assignTask(taskId);
    }

    function onServiceRegistered(uint256 serviceId) external {
        require(msg.sender == address(serviceManager), "Not authorized");
         // run exactly the same logic as after wrapper registration
         tryAssignTaskForService(serviceId);
    }

    function onTaskComplete(uint256 taskId) external {
        require(msg.sender == address(taskManager), "Unauthorized caller");
        uint256 svcId = taskToService[taskId];
        delete taskToService[taskId];
        delete serviceToTask[svcId];    // if you added the reverse mapping
        serviceManager.setBusy(svcId, false);
        tryAssignTaskForService(svcId);
    }

    function assignTask(uint256 taskId) internal {
    (
        ,
        bytes32 taskCategory,
        bytes32 taskType,
        bool taskActive,
        uint256 reward
    ) = taskManager.getTaskMeta(taskId);

    if (!taskActive) return;

    uint256 count = serviceManager.getServiceCount();
    address bestCreator = address(0);
    uint256 lowestPrice = type(uint256).max;
    uint256 bestServiceId;

    for (uint256 i = 0; i < count; i++) {
        (
            uint256 serviceId,
            bytes32 serviceCategory,
            bytes32 serviceType,
            uint256 price,
            address creator,
            bool active,
            bool busy
        ) = serviceManager.getServiceMeta(i+1);
    if (serviceToTask[serviceId] != 0) continue;
    if (
        active && !busy &&
        serviceCategory == taskCategory &&
        serviceType == taskType &&
        price<=reward &&
        price < lowestPrice
        ) {
        lowestPrice = price;
        bestCreator = creator;
        bestServiceId = serviceId;
        }
    }
    if (bestCreator != address(0)) {
        taskToService[taskId] = bestServiceId;
        serviceToTask[bestServiceId] = taskId;
        taskManager.assignTaskExecutor(taskId, bestCreator, lowestPrice);
        serviceManager.setBusy(bestServiceId, true);
    }
    }

    /// look for the single highest‐reward task this new service can execute
    function tryAssignTaskForService(uint256 serviceId) internal {
        ( uint256 svcId, bytes32 svcCat, bytes32 svcType, uint256 price, address svcCreator, bool active, bool busy ) 
            = serviceManager.getServiceMeta(serviceId);
        if (!active || busy) return;

        uint256 taskCount = taskManager.getTotalTasks();
        uint256 bestTaskId;
        uint256 highestReward;

        for (uint256 i = 0; i < taskCount; i++) {
            ( uint256 tId, bytes32 tCat, bytes32 tType, bool tActive, uint256 reward ) 
                = taskManager.getTaskMeta(i+1);
            if (taskToService[tId] != 0) continue;
            if (
                tActive
                && tCat == svcCat
                && tType == svcType
                && reward >= price
                && reward > highestReward
            ) {
                highestReward = reward;
                bestTaskId = tId;
            }
        }

        if (highestReward > 0) {
            taskToService[bestTaskId] = svcId;
            serviceToTask[svcId] = bestTaskId; 
            // assign executor = the service’s creator; pay out at service price
            taskManager.assignTaskExecutor(bestTaskId, svcCreator, price);
            serviceManager.setBusy(serviceId, true);
        }
    }


}
