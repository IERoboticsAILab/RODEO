// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Standard oracle hook interface (optional).
interface IOraclePolicy {
    function canFinalize(address caller) external view returns (bool);
    function normalizeReason(string calldata reason) external pure returns (string memory);
}
