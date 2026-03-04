// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IServiceManager {
    enum ProviderType { Robot, Human, Organization }

    struct Service {
        uint256 id;
        string name;
        string description;

        bytes32 categoryHash;
        bytes32 serviceTypeHash;

        uint256 price;
        address creator;

        bool active;
        ProviderType providerType;
        bool busy;
    }

    function registerService(
        string calldata name,
        string calldata description,
        string calldata category,
        string calldata serviceType,
        uint256 price,
        ProviderType providerType
    ) external returns (uint256 serviceId);

    function removeService(uint256 serviceId) external;
    function activateService(uint256 serviceId) external;

    function setBusy(uint256 serviceId, bool isBusy) external;

    function getService(uint256 serviceId) external view returns (Service memory);

    function getServiceMeta(uint256 serviceId)
        external
        view
        returns (
            uint256 sid,
            bytes32 categoryHash,
            bytes32 serviceTypeHash,
            uint256 price,
            address creator,
            bool active,
            bool busy
        );

    function getServiceCount() external view returns (uint256);
    function getServicesByCreator(address creator) external view returns (uint256[] memory);
}
