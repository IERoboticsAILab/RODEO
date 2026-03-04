// File: contracts/mocks/MockOrganization.sol
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IServiceRegistrationReceiver {
    function onServiceRegistered(uint256 serviceId) external;
    function onServiceRemoved(uint256 serviceId) external;
}

interface IServiceManager {
    function setBusy(uint256 index, bool isBusy) external;
}

/// @dev Minimal IOrganization interface for TaskManager callbacks
interface IOrganization {
    function onTaskRegistered(uint256 taskId) external;
    function onTaskComplete(uint256 taskId) external;
    function checkTaskCancelation(uint256 taskId) external;
}

/// @dev Minimal ITaskManager interface for invoking TaskManager actions
interface ITaskManager {
    function _unassignTask(uint256 taskId) external;
    function assignTaskExecutor(uint256 taskId, address executor, uint256 reward) external;
    function unassignTask(uint256 taskId) external;
    function setOracle(address _oracle) external;
}

/// @dev Mock org that routes calls into TaskManager
contract MockOrganization is IOrganization, IServiceRegistrationReceiver {
    // no-op hooks
    uint256 public registeredCount;
    uint256 public removedCount;
    uint256 public lastServiceId;

    event OrgNotified(uint256 indexed serviceId);

    function onTaskRegistered(uint256) external override {}
    function onTaskComplete(uint256) external override {}

    /// @notice Called by TaskManager unregister logic
    function checkTaskCancelation(uint256 taskId) external override {
        
        ITaskManager(msg.sender)._unassignTask(taskId);
    }

    function callSetBusy(address serviceManagerAddress, uint256 index, bool isBusy) external {
        IServiceManager(serviceManagerAddress).setBusy(index, isBusy);
    }

    function onServiceRegistered(uint256 serviceId) external override {
        registeredCount += 1;
        lastServiceId = serviceId;
        emit OrgNotified(serviceId);
    }
    function onServiceRemoved(uint256) external override {
        removedCount += 1;

    }

    /// @notice Test helper: have org assign a task
    function callAssign(
        address taskManagerAddress,
        uint256 taskId,
        address executor,
        uint256 reward
    ) external {
        ITaskManager(taskManagerAddress).assignTaskExecutor(taskId, executor, reward);
    }

    /// @notice Test helper: have org unassign a task
    function callUnassign(
        address taskManagerAddress,
        uint256 taskId
    ) external {
        ITaskManager(taskManagerAddress).unassignTask(taskId);
    }

    function callSetOracle(address tm, address _oracle) external {
    ITaskManager(tm).setOracle(_oracle);
    }

}