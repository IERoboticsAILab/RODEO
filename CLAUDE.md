# RODEO v2 – notes for Claude Code

Working branch: `rodeo-v2` (on top of `rodeo-ros2`, which holds only the ROS 2
bridge port; `main` is the original ROS 1 RODEO). Commit work here in focused
commits; push only when asked.

## Goal

Any robot (the Husarion Panther now; TIAGo and drones later) joins the RODEO
marketplace by declaring its services and implementing one standard action.
RODEO itself never contains robot-specific code. Use case 1: the Panther
delivers a package between two named places and the recipient confirms.

## Architecture (agreed with Milan)

- **Matching is on-chain** (Organization.assignTask: cheapest active, non-busy
  service of the task's category/type with price <= reward). No central dispatcher.
- **Per robot**: a **bridge** (one wallet, `dao-bridge/ros2-eth-bridge`), an
  **agent** (`robot-agent/.../rodeo_agent`, generic, configured by
  `services.yaml`), and an **executor** (robot-specific, serves
  `/<robot>/rodeo/execute_task`). The Panther's executor will live inside its
  web app (separate repo), so there is one writer to Nav2.
- **One oracle, validators chosen by (category, task type).** The ROS 2 oracle
  (`oracle/ros2_ws/src/rodeo_oracle`, default) runs an `oracle` node plus one
  validator node per service type serving `rodeo_interfaces/srv/ValidateProof`
  (any language). A pure-Python oracle with the same checks (`oracle/oracle_node`,
  compose profile `python`) also exists; both share the logic in `oracle_node/`.
- Proofs are ROS 2 bags (MCAP) with `/rodeo/manifest`, `/rodeo/pose`,
  `/rodeo/events`, `/rodeo/payload_weight`; submitted as
  `file://<path>#sha256=<hash>`. Proof folder: repo `oracle/proofs/`, mounted at
  `/root/oracle/proofs` in the agent, executors and oracle.
- Contracts are unchanged. Anyone can call `TaskManager.registerTask` directly
  (only the Organization wrapper is onlyOwner).

## Decisions and assumptions

- An online robot is assumed able to finish its tasks: failures are logged and
  left for a person (the contract has no hand-back).
- Busy flags are per service; the agent marks the robot's other services busy
  while one runs and frees them at the verdict.
- Agent deactivates its services on shutdown; crashes are handled by a person.
- Delivery proof = poses + events + deck weight + recipient confirmation.
  Trust in robot-reported data is out of scope for now.
- Legacy proofs (ROS 1 .bag, .csv) still accepted while `LEGACY_PROOFS=1`
  (they are not bound to a task).
- Task descriptions: JSON `{"v":1,"params":{...},"note":"..."}`; free text works
  via parameter defaults in `services.yaml`.

## Layout

```
blockchain-network/   ganache-docker (local chain), smart-contracts (Hardhat)
dao-bridge/           ros2-eth-bridge (ROS 2 Humble), org-web (FastAPI + Next.js)
robot-agent/          rodeo_interfaces, rodeo_common (no ROS), rodeo_agent; config/panther/services.yaml
oracle/               oracle_node (pure Python), tests/, proofs/
quick-start/          demo without a robot: agent + fake executor (docker/demo.sh)
scripts/              update-addresses.sh
```

## Running and testing

- Chain: fresh Ganache gives deterministic addresses (already in the configs):
  IECoin 0x5FbD…0aa3, Organization 0x8464…18bC, ServiceManager 0x71C9…292e,
  TaskManager 0x7125…B03e.
- Unit tests (no ROS, no chain):
  - `cd dao-bridge/org-web/backend && python -m pytest tests`
  - `cd robot-agent/ros2_ws/src && PYTHONPATH=rodeo_common:rodeo_agent python -m pytest rodeo_common/test rodeo_agent/test`
  - `cd oracle && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:../robot-agent/ros2_ws/src/rodeo_common python -m pytest tests`
  - ROS 2 oracle reader test (sourced workspace with rodeo_interfaces, rodeo_agent, rodeo_oracle):
    `cd oracle/ros2_ws/src/rodeo_oracle && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:../../..:$PYTHONPATH python -m pytest test`
- End to end: Ganache + deploy, org-web, oracle, ROS 2 bridge, then
  `quick-start/docker/demo.sh build && start`, post a Logistics/ItemTransport
  task (reward 100) in org-web at http://localhost:8080. Pass = agent logs
  `task N: VERIFIED - reward paid`.
- ROS_DOMAIN_ID defaults to 40 and no namespace for bridge, agent and demo.

## Gotchas

- web3 6.11.4 and eth-account 0.13.7 conflict on hexbytes; images install
  eth-account with `--no-deps` (working set: hexbytes 0.3.1). Don't "fix" by
  upgrading one side alone.
- Run the agent as the container's main process, not via `ros2 launch`: a
  SIGTERM to launch left the agent running and skipped its shutdown.
- Several compose files live in folders named `docker`; never use `--remove-orphans`.
- Local-only files: `blockchain-network/ganache-docker/docker-compose.override.yml`
  (chain in `ganache_db_local`), and uncommitted address edits in
  `oracle/docker/.env`, `dao-bridge/org-web/.env`, `deployments/1337.json`.
  Don't commit or overwrite them unless asked.
- `oracle/oracle_node/power_csv.py` and `oracle/docker/.env` have CRLF line endings.
- The contract only re-matches waiting tasks on contract events; setBusy(false)
  does not trigger it, activateService does. The agent therefore takes services
  offline (deactivate) while unavailable and reactivates them afterwards.
- At assignment the contract lowers a task's reward to the service price and
  keeps the excess escrow; always post exactly the price (the agent does).
- Organization.deposit sets (not adds to) the TaskManager allowance: funds
  available after a deposit equal that deposit; leftovers and refunds to the
  Organization are stranded. org-web's deposit approves first, then deposits.

## Status (Nov 2026)

Done on `rodeo-v2` and tested end to end with the fake executor: ROS 2 bridge,
robot standard, agent, ROS 2 oracle (delivery and charging validator nodes;
Python oracle kept as an alternative), charging (station = institution wallet,
battery-triggered requests), org-web task form (Name, Description, Category,
Type, Price; service details after the type; robot-only services hidden) and
Organization task funds on the Home page.

## Next

1. **Panther executor** in the Panther repository's web app, Gazebo twin first,
   then the real robot. Its own `CLAUDE.md` (in that repo) has the plan; the
   RODEO side needs no change except running the bridge and agent on the web
   app's ROS domain (42 in sim, 41 on medusa) with `ROBOT_NAMESPACE=panther`
   and without the fake executor.
2. **WiBotic source** for `station_executor` (real charging measurements), and
   the fee model (flat now; energy tiers next; see robot-agent/README.md §7).
3. **MetaMask** in org-web: people sign and pay from their own wallets
   (approve the TaskManager, then `TaskManager.registerTask`); a Connect wallet
   control in the header with address and IEC balance. The lab's IEcoin site
   (iecoin.cyphy.life, with a faucet) is the reference; its network details
   (RPC URL, chain ID, token address, faucet rules) are still to be collected.
4. **Contract issues to raise with Milan**: excess reward above the service
   price is locked in the TaskManager; `Organization.deposit` sets rather than
   adds the allowance (leftovers and refunds stranded); no way for an executor
   to hand back a task.
5. Later: cleanup group C (old oracle scripts; ask Milan about
   smart-contracts/python and templates), TIAGo and drone executors.

## Working with Samuel's checkout

- `oracle/docker/.env`, `dao-bridge/org-web/.env` and
  `deployments/1337.json` carry the fresh-chain addresses (committed on
  rodeo-v2). `oracle/docker/.env` may have uncommitted local edits.
- Commit only the files a change touches (`git commit <paths>`), never `-a`.
- The Ganache chain lives in `ganache_db_local` via a local override file.
