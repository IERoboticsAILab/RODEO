# Ganache Docker

Local Ethereum blockchain for RODEO development.

## Quick Start

```bash
docker-compose up -d
```

RPC endpoint: `http://localhost:8545`

## Configuration

- **Chain ID:** 1337
- **Accounts:** 20 pre-funded accounts (1000 ETH each)
- **Mnemonic:** `test test test test test test test test test test test junk`
- **Persistence:** Blockchain state saved to `./ganache_db/`

## Account Keys

Pre-generated account addresses and private keys are in [ganache_keys.txt](ganache_keys.txt).

## Commands

```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# View logs
docker logs ganache

# Reset blockchain (delete all state)
docker-compose down && rm -rf ganache_db/
```
