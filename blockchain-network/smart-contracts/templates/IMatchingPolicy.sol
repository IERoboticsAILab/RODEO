// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Pure matching decision interface.
/// @dev Implementations can be cheapest-service, highest-budget-task, fair queue, reputation, etc.
interface IMatchingPolicy {
    /// @return serviceId 0 if no match
    /// @return agreedReward the payout amount to use for assignment (often service price)
    function pickServiceForTask(uint256 taskId) external view returns (uint256 serviceId, uint256 agreedReward);

    /// @return taskId 0 if no match
    /// @return agreedReward the payout amount to use for assignment
    function pickTaskForService(uint256 serviceId) external view returns (uint256 taskId, uint256 agreedReward);
}
