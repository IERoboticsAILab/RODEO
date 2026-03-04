// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

enum TaskStatus { Unassigned, Assigned, Executed }

/// @notice Task registry + escrow + assignment + verification entrypoints.
/// @dev Implementation decides escrow timing, payout timing, refund rules.
interface ITaskManager {
    struct Task {
        uint256 id;
        string description;

        bytes32 categoryHash;
        bytes32 taskTypeHash;

        address creator;

        /// @dev Max budget or posted reward, depending on implementation.
        uint256 reward;

        TaskStatus status;
        address executor;

        bool active;

        string proofURI;
        address oracle;
        bool verified;
    }

    // --- lifecycle ---
    function registerTask(
        string calldata description,
        string calldata category,
        string calldata taskType,
        uint256 reward
    ) external returns (uint256 taskId);

    /// @notice Called by coordinator/org to assign an executor and set price/reward.
    /// @dev reward parameter may represent "agreed payout" (<= posted budget).
    function assignTaskExecutor(uint256 taskId, address executor, uint256 reward) external;

    /// @notice Cancel/rollback assignment and apply refund rules.
    function unassignTask(uint256 taskId) external;

    /// @notice Coordinator-only internal unassign hook (if design needs it).
    function _unassignTask(uint256 taskId) external;

    function removeTask(uint256 taskId) external;
    function activateTask(uint256 taskId) external;

    // --- proof / oracle ---
    function setOracle(address oracle) external;
    function submitProof(uint256 taskId, string calldata proofURI) external;
    function oracleFulfill(uint256 taskId, bool ok, string calldata reason) external;

    // --- views ---
    function getTask(uint256 taskId) external view returns (Task memory);
    function getTaskMeta(uint256 taskId)
        external
        view
        returns (uint256 tId, bytes32 categoryHash, bytes32 taskTypeHash, bool active, uint256 reward);

    function getTotalTasks() external view returns (uint256);
    function getTasksByCreator(address creator) external view returns (uint256[] memory);
}