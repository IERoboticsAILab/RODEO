// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IECoin {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
}

interface IOrganization {
    function onTaskRegistered(uint256 taskId) external;
    function onTaskComplete(uint256 taskId) external;
    function checkTaskCancelation(uint256 taskId) external;
}

enum TaskStatus { Unassigned, Assigned, Executed }

contract TaskManager {
    struct Task {
        uint256 id;
        string description;
        string taskCategory;
        string taskType;
        bytes32 categoryHash;
        bytes32 taskTypeHash;
        address creator;
        uint256 reward;
        TaskStatus status;
        address executor;
        bool active;
        string proofURI;
        address oracle;
        bool verified;
        }

    uint256 public nextTaskId=1;
    Task[] public tasks;
    mapping(address => uint256[]) public creatorToTaskIds;

    IECoin public token;
    IOrganization public organization;
    address public oracle;
    uint256 public constant MAX_REASON_LENGTH = 128;

    // Execution time limit per task category (seconds from assignment; 0 = no limit).
    // Set by the organization, e.g. "Logistics" -> 900 (15 min). Kept outside the
    // Task struct so getTask/getAllTasks keep their ABI.
    mapping(bytes32 => uint256) public categoryTimeout;
    mapping(uint256 => uint256) public assignedAt;    // taskId -> block time of the assignment
    mapping(uint256 => uint256) public taskTimeout;   // taskId -> limit fixed at assignment
    mapping(uint256 => uint256) public proofAt;       // taskId -> block time of the proof (0 = none)

    event TaskRegistered(uint256 taskId, address indexed creator);
    event TaskRemoved(uint256 taskId);
    event TaskRewardPaid(uint256 taskId, address executor, uint256 reward);
    event TaskUnassigned(uint256 indexed taskId);
    event TaskAssigned(uint256 indexed taskId);
    event TaskProofSubmitted(uint256 indexed taskId, address indexed executor, string proofURI);
    event TaskOracleRequested(uint256 indexed taskId, address indexed oracle);
    event TaskVerified(uint256 indexed taskId);
    event TaskRejected(uint256 indexed taskId, string reason); // short reason for indexing
    event TaskTimeoutSet(string category, uint256 timeoutSeconds);
    event TaskExpired(uint256 indexed taskId, uint256 deadline);

    constructor(address tokenAddress, address organizationAddress) {
        token = IECoin(tokenAddress);
        organization = IOrganization(organizationAddress);
    }

    function setOracle(address _oracle) external {
        require(msg.sender == address(organization), "Only org");
        require(_oracle != address(0), "Zero oracle");
        // store once at contract level
        oracle = _oracle;
    }

    function setCategoryTimeout(string calldata category, uint256 timeoutSeconds) external {
        require(msg.sender == address(organization), "Only org");
        categoryTimeout[keccak256(bytes(category))] = timeoutSeconds;
        emit TaskTimeoutSet(category, timeoutSeconds);
    }

    /// Block time by which the proof must be submitted; 0 = not assigned or no limit.
    function deadlineOf(uint256 taskId) public view returns (uint256) {
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        Task storage task = tasks[taskId - 1];
        if (task.status != TaskStatus.Assigned || taskTimeout[taskId] == 0) return 0;
        return assignedAt[taskId] + taskTimeout[taskId];
    }

    /// True when anyone may call expireTask(taskId) now.
    function isExpired(uint256 taskId) public view returns (bool) {
        uint256 d = deadlineOf(taskId);
        return d != 0 && block.timestamp > d && proofAt[taskId] == 0 && tasks[taskId - 1].active;
    }

    /// Past the deadline without a proof: unassign, refund the creator, free the
    /// service, deactivate the task (the same path as unassignTask). Anyone may call
    /// it (the oracle does, every few seconds), since a contract cannot act by itself.
    function expireTask(uint256 taskId) external {
        require(isExpired(taskId), "Task not expired");
        uint256 d = deadlineOf(taskId);
        organization.checkTaskCancelation(taskId);
        emit TaskExpired(taskId, d);
    }

    function getTaskMeta(uint256 taskId) external view returns (uint256 tId, bytes32 categoryHash, bytes32 taskTypeHash, bool active, uint256 reward) {
        //Task storage task = tasks[taskId];
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        Task storage task = tasks[taskId - 1];
        return (task.id, task.categoryHash, task.taskTypeHash, task.active, task.reward);
    }

    function registerTask(string calldata description, string calldata category,  string calldata taskType, uint256 reward) external returns (uint256) {

        bytes32 categoryHash = keccak256(bytes(category));
        bytes32 taskTypeHash = keccak256(bytes(taskType));
        
        Task memory newTask = Task(nextTaskId, description, category, taskType, categoryHash, taskTypeHash, msg.sender, reward, TaskStatus.Unassigned, address(0), true,'none', oracle, false);
        tasks.push(newTask);
        creatorToTaskIds[msg.sender].push(nextTaskId);

                // escrow the reward now
        require(token.allowance(msg.sender, address(this)) >= reward, "Allowance too low when Registering Task");
        bool ok = token.transferFrom(msg.sender, address(this), reward);
        require(ok, "Escrow transfer failed");

        emit TaskRegistered(nextTaskId, msg.sender);
        organization.onTaskRegistered(nextTaskId); // Notify Organization
        return nextTaskId++;
    }

    function assignTaskExecutor(uint256 taskId, address executor, uint256 reward) external {
        require(msg.sender == address(organization), "Not authorized");
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        Task storage task = tasks[taskId - 1];
        require(task.status == TaskStatus.Unassigned, "Already assigned");
        require(task.active, "Task not active");
        // enforce the originally declared reward
        require(reward <= task.reward, "Reward mismatch");

        // make sure escrow is present
        require(token.balanceOf(address(this)) >= task.reward, "Escrow missing");

        task.reward = reward; // update to the agreed reward, can be same or lower than originally posted
        task.executor = executor;
        task.status = TaskStatus.Assigned;
        assignedAt[taskId] = block.timestamp;
        taskTimeout[taskId] = categoryTimeout[task.categoryHash];
        proofAt[taskId] = 0;

        emit TaskAssigned(taskId);
    }

    function _unassignTask(uint256 taskId) external {
        require(msg.sender == address(organization), "Not authorized to unassign task");
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        Task storage task = tasks[taskId - 1];
        require(task.status == TaskStatus.Assigned, "Task not assigned");
        

        // reset task fields
        task.status = TaskStatus.Unassigned;
        task.executor = address(0);

        // refund reward to creator
        bool ok = token.transfer(task.creator, task.reward);
        require(ok, "Refund failed");

        // make it inactive, creator must reactivate to re escrow
        task.active = false;

        emit TaskUnassigned(taskId);
    }

    function unassignTask(uint256 taskId) external {
        organization.checkTaskCancelation(taskId);
    
    }

    function removeTask(uint256 taskId) public {
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        Task storage task = tasks[taskId - 1];
        require(msg.sender == task.creator, "Only creator can remove task");
        require(task.active, "Already removed");
        require(task.status == TaskStatus.Unassigned, "Task is assgned or executed");
        task.active = false;
        emit TaskRemoved(taskId);
    }

    function activateTask(uint256 taskId) public {
        require(taskId > 0 && taskId <= tasks.length, "Invalid index");
        Task storage task = tasks[taskId - 1];
        require(msg.sender == task.creator, "Only creator can activate tasks");
        require(!task.active, "Task already active");

        // pull reward again from creator to escrow
        require(token.allowance(task.creator, address(this)) >= task.reward, "Allowance too low");
        bool ok = token.transferFrom(task.creator, address(this), task.reward);
        require(ok, "Escrow transfer failed");
        task.active = true;
        organization.onTaskRegistered(taskId);
        emit TaskRegistered(taskId, msg.sender);
    }

    function completeTask(uint256 taskId) external {
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        Task storage task = tasks[taskId - 1];
        require(task.active, "Task not active");
        require(msg.sender == address(this), "You are not allowed to complete the task");
        require(task.status == TaskStatus.Assigned, "Task not assigned");
        
        task.status = TaskStatus.Executed;
        task.active = false;

        bool success = token.transfer(task.executor, task.reward);
        require(success, "Reward transfer failed");
        
        organization.onTaskComplete(taskId);
        emit TaskRewardPaid(taskId, task.executor, task.reward);
    }

    function submitProof(uint256 taskId, string calldata proofURI) external {
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        Task storage t = tasks[taskId - 1];
        require(t.active, "Task not active");
        require(t.status == TaskStatus.Assigned, "Not in Assigned");
        require(msg.sender == t.executor, "Only assigned executor");
        require(bytes(proofURI).length > 0, "Bad URI");
        uint256 d = deadlineOf(taskId);
        require(d == 0 || block.timestamp <= d, "Task timed out");

        t.proofURI = proofURI;
        proofAt[taskId] = block.timestamp;

        emit TaskProofSubmitted(taskId, t.executor, proofURI);
        emit TaskOracleRequested(taskId, oracle);
    }

    function oracleFulfill(uint256 taskId, bool ok, string calldata reason) external {
        require(msg.sender == oracle, "Only oracle");
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        Task storage t = tasks[taskId - 1];

        if (ok) {
            t.verified = true;
            this.completeTask(taskId);
            emit TaskVerified(taskId);
            emit TaskRewardPaid(taskId, t.executor, t.reward);
        } else {
            // revert to Unassigned and refund via the existing unassign path
            t.verified = false;
            // reuse your existing refund logic by delegating to Organization
            organization.checkTaskCancelation(taskId);
            emit TaskRejected(taskId, bytes(reason).length <= MAX_REASON_LENGTH ? reason : "");
    }
}

    function getTask(uint256 taskId) public view returns (Task memory) {
        require(taskId > 0 && taskId <= tasks.length, "Invalid task ID");
        return tasks[taskId-1];
    }

    function getTasksByCreator(address creator) public view returns (uint256[] memory) {
        return creatorToTaskIds[creator];
    }

    function getAllTasks() public view returns (Task[] memory) {
        return tasks;
    }

    function getTotalTasks() public view returns (uint256) {
        return tasks.length;
    }
}
