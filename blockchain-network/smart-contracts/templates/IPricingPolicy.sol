// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Defines whether price <= budget is acceptable and what payout should be.
interface IPricingPolicy {
    /// @return ok whether service can match task
    /// @return agreedReward payout amount to executor if matched
    function priceTask(uint256 taskBudget, uint256 servicePrice) external pure returns (bool ok, uint256 agreedReward);
}
