# Oracle Configuration Update Guide

After deploying new smart contracts, you need to update the oracle configuration with the new contract addresses.

## Quick Update (Recommended)

Update the `.env` file in the `oracle/docker/` directory:

```bash
cd oracle/docker
nano .env  # or use your preferred editor
```

Update these key values:

```bash
# Smart Contract Addresses - UPDATE THESE!
ORGANIZATION_ADDRESS=0x...
TASK_MANAGER_ADDRESS=0x...
SERVICE_MANAGER_ADDRESS=0x...
IECOIN_ADDRESS=0x...

# Oracle Wallet - UPDATE IF CHANGED!
ORACLE_ADDRESS=0x...
ORACLE_PRIVATE_KEY=0x...
```

Then restart the oracle:

```bash
./oracle-docker.sh restart
# or
docker compose down && docker compose up -d
```

## Alternative: addresses.json

If you don't set environment variables, the oracle will fall back to using `addresses.json`.

To use this method:
1. Remove or comment out the contract/wallet variables in `.env`
2. Update `oracle/addresses.json` with new addresses
3. No need to rebuild - the file is loaded at runtime

## Configuration Priority

The oracle loads configuration in this order:
1. **Environment variables** (from `.env` file) - HIGHEST PRIORITY
2. **addresses.json** file - FALLBACK

When you start the oracle, you'll see which method is being used:
```
✅ Oracle configuration loaded from environment variables
```
or
```
📄 Oracle configuration loaded from addresses.json
```

## Finding New Contract Addresses

After deploying smart contracts with Hardhat:

```bash
cd blockchain-network/smart-contracts
cat deployments/1337.json
```

This file contains all deployed contract addresses for chain ID 1337 (local Ganache).

## Configuration Files

- `oracle/docker/.env` - Main configuration (environment variables)
- `oracle/docker/.env.example` - Template with default values
- `oracle/addresses.json` - Fallback configuration (JSON format)

## Verification

Check that the oracle is using the correct addresses:

```bash
docker logs rodeo-oracle --tail 20
```

You should see:
- Configuration load message
- "Watching oracle requests and outcomes..."
- TaskManager contract address in logs

## Troubleshooting

**Problem**: Oracle starts but doesn't receive events

**Solution**: Verify contract addresses match your deployment
```bash
# Check what the oracle is using
docker logs rodeo-oracle | grep -i "configuration\|address"

# Compare with actual deployment
cat ../../blockchain-network/smart-contracts/deployments/1337.json
```

**Problem**: Transaction failures with "insufficient funds"

**Solution**: Ensure ORACLE_ADDRESS has enough ETH and the ORACLE_PRIVATE_KEY is correct

**Problem**: Changes to .env not reflected

**Solution**: Restart the container (no rebuild needed for env changes)
```bash
docker compose down && docker compose up -d
```
