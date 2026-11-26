# Deploying RODEO on colossus

RODEO (org-web, oracle, ros2-eth-bridge, agent) runs on **colossus** (`10.205.10.2`),
the lab server that also runs IE Coin, as the Portainer stack **`rodeo`**. The Panther
web app (the robot's RODEO executor) and its zenoh bridge are a second stack,
**`panther-webapp`**, from IERoboticsAILab/robopreneur, branch `panther-webapp`
(its `deploy/DEPLOY.md`).

## Everyday: push to main

A push to `main` runs CI on GitHub (builds the four images, oracle tests). If that
passes, the runner on colossus runs `deploy/ci-deploy.sh`:

1. exports the commit to `/opt/rodeo/releases/<sha>`, where the stack's read-only configs are mounted from
2. builds `rodeo-{org-web,oracle,bridge,agent}:<sha>` on colossus
3. points the Portainer stack `rodeo` at them, keeping the stack's env
4. waits for these health checks:
   - org-web answers `/api/organization/balance`
   - the bridge logs `dao_listener ready` and `dao_writer ready`
   - the oracle logs `Watching oracle requests`
   - the agent logs `ready - waiting for assignments`
5. if the checks fail within 5 minutes, it puts the previous version back and the job fails.

Follow the run in the repo's **Actions** tab. Pull requests and other branches get the
checks only. Nothing is deployed until the repo variable `DEPLOY_ENABLED` is `true`.

| What | Where |
|---|---|
| org-web | https://rodeo.cyphy.life (host nginx → `127.0.0.1:8240`) |
| Stack | Portainer `http://10.205.10.2:9000` → Stacks → `rodeo` |
| Secrets | the stack's Environment variables, plus `/etc/rodeo/wallet_opsepolia.json` |
| Proofs | `/opt/rodeo/proofs`: the web app writes them, the agent hashes them, the oracle reads them |
| State | `/opt/rodeo/state/{org-web,oracle}` (task timer, proofs already used) |
| Logs | `docker logs -f rodeo-oracle` (also `rodeo-agent`, `rodeo-bridge`, `rodeo-org-web`) |

Only one org-web and one oracle may run at a time, anywhere. Two task timers would
unassign tasks twice, and two oracles would verify the same task twice. Stop the PC copies
before colossus goes live.

## One-time setup

You need an account on colossus with sudo and Portainer access (LDAP). From outside the
lab, tunnel first, as in iecoin's DEPLOY.md:
`sshuttle -r <user>@90.166.9.105 10.205.10.0/24 10.205.1.0/24 10.205.3.0/24`.

### 1. Ports

```sh
ssh <ldap-user>@10.205.10.2
sudo ss -ltnp | grep -E ':(8240|8250|7448)\b' || echo "all free"
```

8240 is org-web and 8250 is the Panther web app, both on 127.0.0.1. 7448 is the zenoh
router the Panther connects to. If a port is taken, choose another and change it in:
- `deploy/portainer-stack.yml`
- `deploy/nginx/*.conf`
- the repo variable `ORG_WEB_PORT`

### 2. Folders and the robot keystore

```sh
id gh-runner                        # the runner user IE Coin already uses; must be in the docker group
sudo mkdir -p /opt/rodeo/{releases,proofs,state} /etc/rodeo /etc/rodeo-deploy
sudo chown -R gh-runner: /opt/rodeo
sudo chmod 755 /etc/rodeo
sudo chown gh-runner: /etc/rodeo-deploy && sudo chmod 700 /etc/rodeo-deploy
```

Copy the robot keystore over. It's the same file as `~/.ros_eth/wallet_opsepolia.json`
on the PC, with an empty passphrase.

```sh
# on the PC
scp ~/.ros_eth/wallet_opsepolia.json <ldap-user>@10.205.10.2:/tmp/
# on colossus
sudo install -o root -g root -m 600 /tmp/wallet_opsepolia.json /etc/rodeo/wallet_opsepolia.json
rm /tmp/wallet_opsepolia.json
```

### 3. Secrets for the first deploy

The first deploy creates the stack and reads its env once from this file. From then on
the env lives in Portainer (Stacks → rodeo → Environment variables), and the file can
be deleted. The keys are in Bitwarden: "RODEO Sepolia wallets + contracts".

```sh
sudo -u gh-runner tee /etc/rodeo-deploy/rodeo.env >/dev/null <<'EOF'
ORACLE_PRIVATE_KEY=0x...
ORGANIZATION_WALLET_PRIVATE=0x...
ORG_ADMIN_PIN=...
EOF
sudo chmod 600 /etc/rodeo-deploy/rodeo.env
```

Optional overrides (defaults are in `deploy/portainer-stack.yml`): `RPC_URL`,
`ORG_WEB_PORT`, `START_BLOCK`, `ORG_TASK_TIMEOUTS`, `RODEO_WALLET`, the contract addresses.

### 4. Portainer access token

Portainer (`http://10.205.10.2:9000`, LDAP login) → your user → **My account** →
**Access tokens** → **Add access token** (name it `rodeo-deploy`). Then:

```sh
sudo -u gh-runner tee /etc/rodeo-deploy/portainer.key >/dev/null <<< '<the token>'
sudo chmod 600 /etc/rodeo-deploy/portainer.key
```

Your user must be allowed to create stacks on the local environment. The script uses
endpoint id 2, as IE Coin does. If yours differs, set the repo variable
`PORTAINER_ENDPOINT_ID`.

### 5. The runner

Register a runner for this repo, under the same `gh-runner` user as IE Coin's.
1. On GitHub, open **Settings → Actions → Runners → New self-hosted runner** (Linux, x64).
2. Copy its download commands and token from that page.
3. Run them on colossus:

```sh
sudo mkdir -p /opt/actions-runner/rodeo && sudo chown gh-runner: /opt/actions-runner/rodeo
cd /opt/actions-runner/rodeo
sudo -u gh-runner bash            # then paste the page's "Download" commands (curl … tar xzf …)
sudo -u gh-runner ./config.sh --url https://github.com/IERoboticsAILab/RODEO \
  --token <TOKEN> --name colossus-rodeo --labels colossus,rodeo --unattended
sudo ./svc.sh install gh-runner
sudo ./svc.sh start
```

The runner then shows as **Idle** under Settings → Actions → Runners.

### 6. GitHub settings (repo admin)

This repo is **public**, so lock the runner down:
- **Settings → Environments → New environment `production`**: deployment branches = `main` only.
- **Settings → Actions → General → Fork pull request workflows**: "Require approval for all outside collaborators".
- **Settings → Secrets and variables → Actions → Variables**: `DEPLOY_ENABLED` = `true` (do this last, when steps 1–5 are done).

The workflow already runs the deploy job only for pushes to `main`, never for pull requests.

### 7. nginx and DNS

```sh
sudo tee /etc/nginx/sites-available/rodeo.cyphy.life < /opt/rodeo/releases/<sha>/deploy/nginx/rodeo.cyphy.life.conf >/dev/null
sudo ln -s /etc/nginx/sites-available/rodeo.cyphy.life /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Use any release folder, or a checkout. Ask for a Pi-hole record `rodeo.cyphy.life → 10.205.10.2`, as for
iecoin.cyphy.life. There is no public DNS.

### 8. First deploy

1. Stop RODEO on the PC: org-web, oracle, bridge and agent.
2. Set `DEPLOY_ENABLED=true`, then push to `main`, or re-run the latest CI run on `main` (**Actions** → CI → Re-run).
3. Check `https://rodeo.cyphy.life`.
4. Delete `/etc/rodeo-deploy/rodeo.env` once the stack exists.

## By hand (if the runner is down)

On colossus, from a checkout of the commit, as a user in the docker group with read
access to the token:

```sh
sudo -u gh-runner bash -c 'cd /tmp && rm -rf rodeo-manual &&
  git clone https://github.com/IERoboticsAILab/RODEO.git rodeo-manual &&
  cd rodeo-manual && git checkout <commit> && deploy/ci-deploy.sh'
```

## Rollback

The deploy rolls back by itself when the health checks fail. To go back by choice,
re-run the deploy job of an older commit (Actions → that run → Re-run jobs). Its
images and release folder are kept for the last five deploys.
