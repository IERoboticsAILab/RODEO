// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface ICoordinator {
    // --- wiring ---
    function setTaskManager(address tm) external;
    function setServiceManager(address sm) external;
    function setOracle(address oracle) external;

    // --- task/service wrapper (optional pattern) ---
    function registerTask(string calldata description, string calldata category, string calldata taskType, uint256 reward)
        external
        returns (uint256);

    function registerService(
        string calldata name,
        string calldata description,
        string calldata category,
        string calldata serviceType,
        uint256 price,
        uint8 providerType
    ) external returns (uint256);

    function unassignTask(uint256 taskId) external;
    function removeTask(uint256 taskId) external;
    function removeService(uint256 serviceId) external;
    function activateTask(uint256 taskId) external;
    function activateService(uint256 serviceId) external;

    // --- callbacks / hooks ---
    /// @notice Called by TaskManager after task creation (or reactivation).
    function onTaskRegistered(uint256 taskId) external;

    /// @notice Called by TaskManager after completion.
    function onTaskComplete(uint256 taskId) external;

    /// @notice Called by ServiceManager after service creation (or reactivation).
    function onServiceRegistered(uint256 serviceId) external;

    /// @notice Called by ServiceManager after removal (optional).
    function onServiceRemoved(uint256 serviceId) external;

    /// @notice Called by TaskManager when it needs cancellation/unassign logic.
    function checkTaskCancelation(uint256 taskId) external;
}
