// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IServiceRegistrationReceiver {
    function onServiceRegistered(uint256 serviceId) external;
    function onServiceRemoved(uint256 serviceId) external;
}

contract ServiceManager {
    enum ProviderType { Robot, Human, Organization }
    struct Service {
        uint256 id;
        string name;
        string description;
        string serviceCategory;
        string serviceType;
        bytes32 categoryHash;
        bytes32 serviceTypeHash;
        uint256 price;
        address creator;
        bool active;
        ProviderType providerType;
        bool  busy; 
    }

    Service[] public services;
    mapping(address => uint256[]) public creatorToServiceIds;
        // the only contract allowed to flip busy/free
    address public organizationAddress;
    IServiceRegistrationReceiver public organization;

    event ServiceRegistered(uint256 indexed serviceId, address indexed creator);
    event ServiceRemoved(uint256 index);
    event ServiceBusyUpdated(uint256 indexed serviceId, bool busy);

    modifier onlyOrganization() {
        require(msg.sender == organizationAddress, "Not org");
        _;
    }

    constructor(address _organization) {
        organizationAddress = _organization;
        organization = IServiceRegistrationReceiver(_organization);
    }

        function getServiceMeta(uint256 index) external view returns (uint256 sid, bytes32 categoryHash,  bytes32 serviceTypeHash, uint256 price, address creator, bool active, bool busy) {
        require(index > 0 && index <= services.length, "Invalid index");
        Service storage svc = services[index-1];
        return (svc.id, svc.categoryHash, svc.serviceTypeHash, svc.price, svc.creator, svc.active, svc.busy);
    }

    function registerService(
        string calldata name,
        string calldata description,
        string calldata category,
        string calldata serviceType,
        uint256 price,
        ProviderType providerType
        
    ) external returns (uint256) {
        bytes32 categoryHash = keccak256(bytes(category));
        bytes32 serviceTypeHash = keccak256(bytes(serviceType));
        Service memory newService;
        newService.id=services.length + 1;
        newService.name = name;
        newService.description = description;
        newService.serviceCategory=category;
        newService.serviceType=serviceType;
        newService.categoryHash = categoryHash;
        newService.serviceTypeHash = serviceTypeHash;
        newService.price = price;
        newService.creator = msg.sender;
        newService.active = true;
        newService.providerType = providerType;
        newService.busy=false;
        services.push(newService);
        creatorToServiceIds[msg.sender].push(newService.id);
        emit ServiceRegistered(newService.id, msg.sender);
        organization.onServiceRegistered(newService.id);
        return newService.id;
    }

    function removeService(uint256 index) public {
        require(index > 0 && index <= services.length, "Invalid index");
        Service storage service = services[index-1];
        require(msg.sender == service.creator, "Only creator can remove service");
        require(service.active, "Already removed");
        require(!service.busy, "Cant remove busy service. First unassing task");

        service.active = false;
        service.busy = false;
        emit ServiceRemoved(index);
    }

    function activateService(uint256 index) public {
        require(index > 0 && index <= services.length, "Invalid index");
        Service storage service = services[index-1];
        require(msg.sender == service.creator, "Only creator can activate service");
        require(!service.active && !service.busy, "Already active or service is busy");

        service.active = true;
        service.busy = false;
        organization.onServiceRegistered(index);
        emit ServiceRegistered(index, service.creator);
    }

    function getService(uint256 index) public view returns (Service memory) {
        require(index > 0 && index <= services.length, "Invalid index");
        return services[index-1];
    }

    function getServiceCount() public view returns (uint256) {
        return services.length;
    }

    function getAllServices() public view returns (Service[] memory) {
        return services;
    }

    function getServicesByCreator(address creator) public view returns (uint256[] memory) {
        return creatorToServiceIds[creator];
    }

        /// owner of that service marks it busy or free
    function setBusy(uint256 index, bool isBusy) external
    {
        require(index > 0 && index <= services.length, "Invalid index");
        Service storage s = services[index-1];
        require(s.active, "Service not active!");
        require(s.creator==msg.sender || msg.sender==address(organization), "Only service creators or organization can set a service as busy");
        s.busy = isBusy;
        emit ServiceBusyUpdated(index, isBusy);
    }
}
