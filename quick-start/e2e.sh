#!/usr/bin/env bash
# RODEO end-to-end test on a fresh local chain: one delivery task from posting to payment,
# with the fake executor standing in for the robot. Everything RODEO is in this repo:
#
#   Ganache (fresh) -> contracts deployed -> org-web, oracle, bridge (robot wallet),
#   agent + fake executor -> a Delivery task posted through org-web's API ->
#   pass when the agent logs "VERIFIED - reward paid".
#
# It is isolated from anything else on the machine (its own container names, a docker
# network, Ganache on 127.0.0.1:$E2E_RPC_PORT, org-web on 127.0.0.1:$E2E_WEB_PORT, ROS
# domains 87/88 on loopback only, a temp folder for keys and proofs) and cleans up after
# itself. CI runs it on every push (.github/workflows/ci.yml).
#
#   quick-start/e2e.sh                 # builds the images, runs the test
#   E2E_TAG=ci quick-start/e2e.sh      # use already built rodeo-{org-web,oracle,bridge,agent}:ci
#   E2E_KEEP=1 quick-start/e2e.sh      # leave the containers running afterwards (to look around)
#
# Only Ganache's public development keys are used (blockchain-network/smart-contracts/.env).
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
P=rodeo-e2e
TAG=${E2E_TAG:-e2e}
RPC_PORT=${E2E_RPC_PORT:-18545}
WEB_PORT=${E2E_WEB_PORT:-18080}
TIMEOUT_S=${E2E_TIMEOUT_S:-600}
PIN=e2e-pin
TMP=$(mktemp -d "${TMPDIR:-/tmp}/rodeo-e2e.XXXXXX")
CONTAINERS=($P-ganache $P-org-web $P-oracle $P-bridge $P-agent $P-executor)
# DDS on loopback only, with unicast discovery (as on colossus)
CYCLONE='<CycloneDDS><Domain Id="any"><General><Interfaces><NetworkInterface name="lo"/></Interfaces><AllowMulticast>false</AllowMulticast></General><Discovery><ParticipantIndex>auto</ParticipantIndex><MaxAutoParticipantIndex>100</MaxAutoParticipantIndex><Peers><Peer Address="127.0.0.1"/></Peers></Discovery></Domain></CycloneDDS>'

say() { echo -e "\n==> $*"; }
dev_key() { grep -E "^$1=" blockchain-network/smart-contracts/.env | cut -d= -f2; }

cleanup() {
  local rc=$?
  if [ $rc -ne 0 ]; then
    say "FAILED: last logs"
    for c in "${CONTAINERS[@]}"; do
      echo "----- $c"; docker logs --tail 40 "$c" 2>&1 || true
    done
  fi
  if [ "${E2E_KEEP:-0}" = 1 ]; then
    say "E2E_KEEP=1: containers left running (docker rm -f ${CONTAINERS[*]}; docker network rm $P; rm -rf $TMP)"
  else
    docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
    docker network rm $P >/dev/null 2>&1 || true
    # proofs and keys were written by root inside containers
    docker run --rm -v "$TMP:/t" --entrypoint sh "rodeo-agent:$TAG" -c 'rm -rf /t/*' >/dev/null 2>&1 || true
    rm -rf "$TMP" 2>/dev/null || true
  fi
  exit $rc
}
trap cleanup EXIT

docker rm -f "${CONTAINERS[@]}" >/dev/null 2>&1 || true
docker network rm $P >/dev/null 2>&1 || true

if [ "$TAG" = e2e ]; then
  say "Building images (set E2E_TAG to reuse built ones)"
  docker build -q -f dao-bridge/org-web/Dockerfile --build-arg NEXT_PUBLIC_API_BASE=/api -t rodeo-org-web:e2e .
  docker build -q -f oracle/docker/Dockerfile -t rodeo-oracle:e2e .
  docker build -q -f dao-bridge/ros2-eth-bridge/docker/Dockerfile -t rodeo-bridge:e2e dao-bridge/ros2-eth-bridge
  docker build -q -f robot-agent/docker/Dockerfile -t rodeo-agent:e2e .
fi
docker build -q -t $P-ganache blockchain-network/ganache-docker >/dev/null
docker build -q -f blockchain-network/smart-contracts/docker/Dockerfile -t $P-deployer blockchain-network/smart-contracts >/dev/null

say "Fresh Ganache on 127.0.0.1:$RPC_PORT"
docker network create $P >/dev/null
docker run -d --name $P-ganache --network $P -p "127.0.0.1:$RPC_PORT:8545" $P-ganache >/dev/null
for i in $(seq 30); do
  curl -sf -X POST "http://127.0.0.1:$RPC_PORT" -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' >/dev/null && break
  sleep 1
done

say "Deploying the contracts"
mkdir -p "$TMP/deployments" "$TMP/proofs" "$TMP/state" "$TMP/org-state" "$TMP/keys"
docker run --rm --network host -e GANACHE_URL="http://127.0.0.1:$RPC_PORT" \
  -v "$TMP/deployments:/app/deployments" $P-deployer > "$TMP/deploy.log" 2>&1 \
  || { cat "$TMP/deploy.log"; exit 1; }
eval "$(python3 - "$TMP/deployments/1337.json" <<'PY'
import json, sys
c = json.load(open(sys.argv[1]))["contracts"]
for k, n in [("IEC", "IECoin"), ("ORG", "Organization"), ("TM", "TaskManager"), ("SM", "ServiceManager")]:
    print(f"{k}={c[n]['address']}")
PY
)"
echo "IECoin $IEC  Organization $ORG  TaskManager $TM  ServiceManager $SM"

say "Robot keystore (Ganache account #4, no passphrase)"
printf '\n' | docker run --rm -i -v "$ROOT/dao-bridge/ros2-eth-bridge/scripts:/s:ro" -v "$TMP/keys:/k" \
  --entrypoint python3 "rodeo-bridge:$TAG" /s/make_wallet.py --out /k/wallet.json >/dev/null 2>&1
[ -s "$TMP/keys/wallet.json" ] || { echo "keystore not created"; exit 1; }
# the bridge's Ganache config, pointed at this chain (only the contracts: block changes)
IEC=$IEC ORG=$ORG TM=$TM SM=$SM RPC_PORT=$RPC_PORT python3 - dao-bridge/ros2-eth-bridge/docker/configs/dao.yaml > "$TMP/dao.yaml" <<'PY'
import os, re, sys
new = {"iecoin": os.environ["IEC"], "organization": os.environ["ORG"],
       "task_manager": os.environ["TM"], "service_manager": os.environ["SM"]}
block = None
for line in open(sys.argv[1]):
    if re.match(r"^\S", line):
        block = line.split(":")[0].strip()
    m = re.match(r"^(\s+)(\w+):", line)
    if block == "contracts" and m and m.group(2) in new:
        line = f'{m.group(1)}{m.group(2)}: "{new[m.group(2)]}"\n'
    line = line.replace("127.0.0.1:8545", f"127.0.0.1:{os.environ['RPC_PORT']}")
    sys.stdout.write(line)
PY

ROS_ENV=(-e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp -e CYCLONEDDS_URI="$CYCLONE")
ROBOT_ENV=(-e ROS_DOMAIN_ID=87 -e ROBOT_NAMESPACE=panther "${ROS_ENV[@]}")

say "org-web on 127.0.0.1:$WEB_PORT"
docker run -d --name $P-org-web --network $P -p "127.0.0.1:$WEB_PORT:80" \
  -e RPC_URL=http://$P-ganache:8545 -e ORGANIZATION_ADDRESS="$ORG" -e IECOIN_ADDRESS="$IEC" \
  -e ORGANIZATION_WALLET_PUBLIC=0x70997970C51812dc3A010C7d01b50e0d17dc79C8 \
  -e ORGANIZATION_WALLET_PRIVATE="$(dev_key PRIVATE_KEY_ORGANIZATION)" -e ORG_ADMIN_PIN=$PIN \
  -e ABI_ROOT=contracts -e ADDRESSES_JSON=addresses.json -e NEXT_PUBLIC_API_BASE=/api \
  -v "$ROOT/dao-bridge/org-web/backend/contracts:/app/contracts:ro" -v "$TMP/org-state:/app/state" \
  "rodeo-org-web:$TAG" >/dev/null

say "Oracle"
docker run -d -t --name $P-oracle --network host \
  -e ROS_DOMAIN_ID=88 "${ROS_ENV[@]}" -e RPC_URL="http://127.0.0.1:$RPC_PORT" \
  -e ORGANIZATION_ADDRESS="$ORG" -e TASK_MANAGER_ADDRESS="$TM" -e SERVICE_MANAGER_ADDRESS="$SM" \
  -e IECOIN_ADDRESS="$IEC" -e ORACLE_ADDRESS=0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC \
  -e ORACLE_PRIVATE_KEY="$(dev_key PRIVATE_KEY_ORACLE)" -e ADDRESSES_JSON=/workspace/addresses.json \
  -e BASE_ABI=/workspace/abi -e TASK_MANAGER_NAME=TaskManager -e CLOCK_CHECK=duration \
  -e EVENT_POLL_SEC=2 -e STATE_DIR=/workspace/state \
  -v "$ROOT/dao-bridge/ros2-eth-bridge/ros2_ws/src/ros_eth_bridge/abi:/workspace/abi:ro" \
  -v "$TMP/proofs:/workspace/proofs:ro" -v "$TMP/proofs:/root/oracle/proofs:ro" -v "$TMP/state:/workspace/state" \
  "rodeo-oracle:$TAG" >/dev/null

say "Robot: bridge, agent, fake executor (namespace panther, ROS domain 87)"
docker run -d --name $P-bridge --network host "${ROBOT_ENV[@]}" -e OWN_ASSIGNMENTS_ONLY=true \
  -e ROS_ETH_DAO_YAML=/config/dao.yaml -v "$TMP/dao.yaml:/config/dao.yaml:ro" \
  -v "$TMP/keys/wallet.json:/root/.ros_eth/wallet.json:ro" "rodeo-bridge:$TAG" >/dev/null
docker run -d --name $P-executor --network host "${ROBOT_ENV[@]}" -e PROOF_MODE=rodeo \
  -v "$ROOT/robot-agent/config/panther/services.yaml:/config/services.yaml:ro" -v "$TMP/proofs:/root/oracle/proofs" \
  "rodeo-agent:$TAG" fake-executor >/dev/null
docker run -d --name $P-agent --network host "${ROBOT_ENV[@]}" \
  -v "$ROOT/robot-agent/config/panther/services.yaml:/config/services.yaml:ro" -v "$TMP/proofs:/root/oracle/proofs" \
  "rodeo-agent:$TAG" agent >/dev/null

wait_log() {  # container text seconds
  local end=$((SECONDS + $3))
  until docker logs "$1" 2>&1 | grep -q "$2"; do
    [ $SECONDS -lt $end ] || { echo "timed out waiting for '$2' in $1"; return 1; }
    docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null | grep -q true || { echo "$1 stopped"; return 1; }
    sleep 3
  done
}
wait_log $P-bridge "dao_writer ready" 120
wait_log $P-oracle "Watching oracle requests" 120
wait_log $P-agent "ready - waiting for assignments" 180
for i in $(seq 30); do curl -sf "http://127.0.0.1:$WEB_PORT/api/organization/balance" >/dev/null && break; sleep 2; done

say "Posting a Delivery task through org-web"
curl -sf -X POST "http://127.0.0.1:$WEB_PORT/api/tasks/register" -H 'Content-Type: application/json' \
  -H "X-Admin-Pin: $PIN" -d '{"title":"e2e delivery","category":"Logistics","taskType":"ItemTransport",
  "rewardIec":100,"params":{"pickup":"package_pickup","dropoff":"package_dropoff","sender":"e2e","recipient":"e2e"}}'
echo

say "Waiting for the oracle's verdict and the payment (up to $TIMEOUT_S s)"
wait_log $P-agent "VERIFIED - reward paid" "$TIMEOUT_S"
docker logs $P-agent 2>&1 | grep -E "assigned|done in|submit proof|VERIFIED" | tail -6
say "PASS: task posted, delivered by the fake executor, approved by the oracle, reward paid"
