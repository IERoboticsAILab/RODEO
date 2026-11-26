#!/usr/bin/env bash
# Automatic deploy of RODEO to colossus, run by the GitHub runner there after CI passes
# on main (.github/workflows/ci.yml). Same idea as IE Coin's deploy/ci-deploy.sh:
#   1. export this commit to /opt/rodeo/releases/<sha> (the stack's read-only configs)
#   2. build the four images, tagged with the commit
#   3. point the Portainer stack "rodeo" at them (stack env kept as is); the first run
#      creates the stack, with its env read once from $FIRST_ENV
#   4. health checks; if they fail, put the previous version back and fail the job
#   5. keep the five newest image tags and releases
#
# Needs (one-time setup, deploy/DEPLOY.md): the Portainer access token in $TOKEN_FILE
# (readable by the runner user only), /opt/rodeo owned by the runner user, and the
# robot keystore at /etc/rodeo/wallet_opsepolia.json.
set -euo pipefail

export STACK=rodeo
export PORTAINER=${PORTAINER:-http://127.0.0.1:9000}
export ENDPOINT_ID=${PORTAINER_ENDPOINT_ID:-2}
export TOKEN_FILE=${TOKEN_FILE:-/etc/rodeo-deploy/portainer.key}
export FIRST_ENV=${FIRST_ENV:-/etc/rodeo-deploy/rodeo.env}
export ORG_WEB_PORT=${ORG_WEB_PORT:-8240}
export HEALTH_TIMEOUT_S=${HEALTH_TIMEOUT_S:-300}
ROOT=/opt/rodeo
SHA=$(git rev-parse --short=7 HEAD)
export SHA

[ -r "$TOKEN_FILE" ] || { echo "::error::No Portainer token at $TOKEN_FILE"; exit 1; }
[ -w "$ROOT" ] || { echo "::error::$ROOT is missing or not writable by $(id -un)"; exit 1; }
[ -e /etc/rodeo/wallet_opsepolia.json ] || { echo "::error::No robot keystore at /etc/rodeo/wallet_opsepolia.json"; exit 1; }

echo "::group::Release $ROOT/releases/$SHA"
mkdir -p "$ROOT/releases" "$ROOT/proofs" "$ROOT/state/org-web" "$ROOT/state/oracle"
if [ ! -d "$ROOT/releases/$SHA" ]; then
  tmp=$(mktemp -d "$ROOT/releases/.tmp-XXXXXX")
  git archive HEAD | tar -x -C "$tmp"
  chmod 755 "$tmp"
  mv "$tmp" "$ROOT/releases/$SHA"
fi
echo "::endgroup::"

build() {  # name dockerfile context [args...]
  local name=$1 file=$2 ctx=$3; shift 3
  echo "::group::Build $name:$SHA"
  docker build -f "$file" "$@" -t "$name:$SHA" "$ctx"
  echo "::endgroup::"
}
build rodeo-org-web dao-bridge/org-web/Dockerfile . --build-arg NEXT_PUBLIC_API_BASE=/api
build rodeo-oracle  oracle/docker/Dockerfile .
build rodeo-bridge  dao-bridge/ros2-eth-bridge/docker/Dockerfile dao-bridge/ros2-eth-bridge
build rodeo-agent   robot-agent/docker/Dockerfile .

export DEPLOY_STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)

python3 - <<'PY'
import json, os, subprocess, sys, time, urllib.error, urllib.request

sha, stack_name = os.environ["SHA"], os.environ["STACK"]
base, endpoint = os.environ["PORTAINER"], int(os.environ["ENDPOINT_ID"])
token = open(os.environ["TOKEN_FILE"]).read().strip()
port = os.environ["ORG_WEB_PORT"]

def api(method, path, body=None, ok404=False):
    req = urllib.request.Request(base + path, method=method,
                                 headers={"X-API-Key": token, "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        if ok404 and e.code == 404:
            return None
        sys.exit(f"::error::Portainer {method} {path}: {e.code} {e.read()[:300]!r}")

template = open("deploy/portainer-stack.yml").read()
if "__SHA__" not in template:
    sys.exit("::error::deploy/portainer-stack.yml has no __SHA__ placeholder")
compose = template.replace("__SHA__", sha)

stack = next((s for s in api("GET", "/api/stacks")
              if s.get("Name") == stack_name and s.get("EndpointId") == endpoint), None)
old_compose = None
if stack is None:
    # First deploy: create the stack, with its env (secrets) from FIRST_ENV. From then
    # on the env lives in Portainer (Stacks -> rodeo -> Environment variables).
    env_file = os.environ["FIRST_ENV"]
    if not os.path.isfile(env_file):
        sys.exit(f"::error::No stack '{stack_name}' in Portainer and no {env_file} to create it from")
    env = []
    for line in open(env_file):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env.append({"name": k.strip(), "value": v.strip()})
    body = {"name": stack_name, "stackFileContent": compose, "env": env}
    print(f"Creating stack {stack_name} at {sha}")
    created = api("POST", f"/api/stacks/create/standalone/string?endpointId={endpoint}", body, ok404=True)
    if created is None:   # Portainer older than 2.19
        created = api("POST", f"/api/stacks?type=2&method=string&endpointId={endpoint}", body)
    stack_id, env = created["Id"], created.get("Env") or env
    print(f"::notice::Stack created (id {stack_id}). You can now delete {env_file}; the env is kept in Portainer.")
else:
    stack_id, env = stack["Id"], stack.get("Env") or []
    old_compose = api("GET", f"/api/stacks/{stack_id}/file")["StackFileContent"]
    print(f"Updating stack {stack_name} (id {stack_id}) to {sha}")
    api("PUT", f"/api/stacks/{stack_id}?endpointId={endpoint}",
        {"stackFileContent": compose, "env": env, "prune": False, "pullImage": False})

# ------------------------------------------------------------------ health checks
since = os.environ["DEPLOY_STARTED"]
need_logs = {
    "rodeo-bridge": ["dao_listener ready", "dao_writer ready"],
    "rodeo-oracle": ["Watching oracle requests"],
    "rodeo-agent": ["ready - waiting for assignments"],
}

def running_tag(name):
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}} {{.Config.Image}}", name],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""

def logs(name):
    r = subprocess.run(["docker", "logs", "--since", since, name], capture_output=True, text=True)
    return r.stdout + r.stderr

def problems():
    out = []
    for name in ["rodeo-org-web", *need_logs]:
        state = running_tag(name)
        if not state.startswith("true ") or not state.endswith(f":{sha}"):
            out.append(f"{name}: not running at {sha} ({state or 'missing'})")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/organization/balance", timeout=10) as r:
            if r.status != 200:
                out.append(f"org-web: /api/organization/balance returned {r.status}")
    except Exception as e:  # noqa: BLE001
        out.append(f"org-web: /api/organization/balance: {e}")
    for name, lines in need_logs.items():
        text = logs(name)
        out += [f"{name}: no '{l}' yet" for l in lines if l not in text]
    return out

deadline = time.time() + int(os.environ["HEALTH_TIMEOUT_S"])
while True:
    left = problems()
    if not left:
        break
    if time.time() > deadline:
        print("::group::Last logs")
        for name in ["rodeo-org-web", *need_logs]:
            print(f"----- {name}\n" + "\n".join(logs(name).splitlines()[-30:]))
        print("::endgroup::")
        for p in left:
            print(f"::error::{p}")
        if old_compose is not None:
            print("Rolling back to the previous version")
            api("PUT", f"/api/stacks/{stack_id}?endpointId={endpoint}",
                {"stackFileContent": old_compose, "env": env, "prune": False, "pullImage": False})
            sys.exit("::error::Deploy failed its health checks; the previous version is running again")
        sys.exit("::error::First deploy failed its health checks (nothing to roll back to)")
    time.sleep(5)
print(f"Live: {sha}")
PY

# Keep the five newest tags of each image and the five newest releases (in-use images
# can't be removed anyway; the running release is always among the newest).
for img in rodeo-org-web rodeo-oracle rodeo-bridge rodeo-agent; do
  docker images "$img" --format '{{.Tag}}' | grep -vx "$SHA" | tail -n +5 | while read -r tag; do
    docker rmi "$img:$tag" >/dev/null 2>&1 || true
  done
done
ls -1t "$ROOT/releases" | grep -vx "$SHA" | tail -n +5 | while read -r rel; do
  rm -rf "${ROOT:?}/releases/$rel"
done
