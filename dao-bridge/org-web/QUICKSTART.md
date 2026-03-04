# Organization Web Console - Quick Start

## Prerequisites Check

- ✅ Docker and Docker Compose V2 installed
- ✅ Blockchain running (Ganache at `http://10.205.10.9:8545`)
- ✅ Smart contracts deployed
- ✅ Contract addresses from deployment

## Quick Start (3 Steps)

### Step 1: Configure Environment

```bash
cd /home/lab/repos/robotic_decentralized_organization/dao-bridge/org-web

# Copy and edit configuration
cp .env.example .env
nano .env  # or your preferred editor
```

**Required values in .env:**
```bash
RPC_URL=http://10.205.10.9:8545
ORGANIZATION_ADDRESS=0xcEC91d876E8f003110D43381359b1bAd124e7F2b
IECOIN_ADDRESS=0x0B306BF915C4d645ff596e518fAf3F9669b97016
ORGANIZATION_WALLET_PUBLIC=0x70997970C51812dc3A010C7d01b50e0d17dc79C8
ORGANIZATION_WALLET_PRIVATE=0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d
```

**Where to find these values:**
- **Contract addresses**: `blockchain-network/smart-contracts/deployments/1337.json`
- **Wallet credentials**: Your deployment addresses file
- **RPC_URL**: Your blockchain endpoint

### Step 2: Build and Start

```bash
./org-web-docker.sh build
./org-web-docker.sh start
```

Or manually:
```bash
docker compose up -d --build
```

**Build time**: ~3-5 minutes (first time)

### Step 3: Access Console

Open browser:
```
http://localhost:8080
```

You should see the Organization Web Console with:
- Tasks panel
- Services panel
- Token balances

## Helper Script Commands

```bash
./org-web-docker.sh build     # Build image
./org-web-docker.sh start     # Start container
./org-web-docker.sh stop      # Stop container
./org-web-docker.sh restart   # Restart
./org-web-docker.sh logs      # View logs
./org-web-docker.sh shell     # Open bash shell
./org-web-docker.sh status    # Show status
./org-web-docker.sh test      # Test blockchain connection
./org-web-docker.sh config    # Show configuration
./org-web-docker.sh clean     # Remove container
./org-web-docker.sh rebuild   # Full rebuild
```

## Verify It's Working

### 1. Check Container Status

```bash
./org-web-docker.sh status
```

Should show: `running` and `healthy`

### 2. Test Blockchain Connection

```bash
./org-web-docker.sh test
```

Should show:
```
Connected: True
Block number: XX
Organization: 0x...
IECoin: 0x...
```

### 3. Check Web Interface

Visit `http://localhost:8080` and verify:
- ✅ Page loads without errors
- ✅ Tasks section visible
- ✅ Services section visible
- ✅ No console errors in browser DevTools

### 4. Test API

```bash
curl http://localhost:8080/contracts
```

Should return contract addresses JSON.

## Common Operations

### Register a New Task

1. Go to Tasks section
2. Click "Register New Task"
3. Fill in:
   - Description: "Delivery to room 301"
   - Proof type: "bag" or "csv"
   - Reward: 100 IEC (minimum 1)
   - Category: 1
4. Click Submit

### Register a Service

1. Go to Services section
2. Click "Register Service"
3. Fill in details and submit

### Check Organization Balance

1. Navigate to Organization section
2. View balance
3. Use Deposit button to add funds if needed

## Troubleshooting

### Container Won't Start

**View logs:**
```bash
./org-web-docker.sh logs
```

**Common issues:**

1. **"Cannot connect to blockchain"**
   ```bash
   # Test RPC connection
   curl -X POST http://10.205.10.9:8545 \
     -H "Content-Type: application/json" \
     --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
   ```

2. **"ABI not found"**
   ```bash
   # Check ABI files exist
   ls -la backend/contracts/
   ```
   Should see `Organization.sol/`, `IECoin.sol/`, etc.

3. **"Organization wallet not configured"**
   - Verify .env has all wallet variables set
   - Check no typos in variable names

### Port Already in Use

Change port in `.env`:
```bash
HOST_PORT=8081
```

Then restart:
```bash
./org-web-docker.sh restart
```

### Can't Create Tasks

**Error: "Insufficient funds"**

Solution: Fund the organization contract:
```bash
# Via web UI: Organization → Deposit → Enter amount → Submit
# Or via API:
curl -X POST http://localhost:8080/organization/deposit \
  -H "Content-Type: application/json" \
  -d '{"amountIec": 1000}'
```

### Page Not Loading

1. **Check container is running:**
   ```bash
   docker ps | grep org-web-console
   ```

2. **Check all services started:**
   ```bash
   docker exec org-web-console ps aux
   ```
   Should see: nginx, uvicorn (Python), node (Next.js)

3. **Check nginx logs:**
   ```bash
   docker exec org-web-console cat /var/log/nginx/error.log
   ```

### API Errors in Browser Console

1. **CORS errors**: Usually fine, nginx handles same-origin
2. **Connection refused**: Check NEXT_PUBLIC_API_BASE in .env
3. **404 errors**: Verify backend is running

## Update After Code Changes

```bash
./org-web-docker.sh rebuild
```

This will:
1. Stop container
2. Rebuild image from scratch
3. Start with new code

## View Logs

Real-time:
```bash
./org-web-docker.sh logs
```

Last 100 lines:
```bash
docker compose logs --tail=100 org-web
```

Specific service:
```bash
# Backend logs
docker exec org-web-console tail -f /var/log/supervisor/uvicorn*

# Nginx logs
docker exec org-web-console tail -f /var/log/nginx/access.log
```

## Environment Variables Reference

### Required

- `RPC_URL` - Blockchain RPC endpoint
- `ORGANIZATION_ADDRESS` - Organization contract
- `IECOIN_ADDRESS` - IECoin token contract
- `ORGANIZATION_WALLET_PUBLIC` - Org wallet address
- `ORGANIZATION_WALLET_PRIVATE` - Org wallet private key

### Optional

- `HOST_PORT` - Port to expose (default: 8080)
- `NEXT_PUBLIC_API_BASE` - Frontend API URL (default: http://localhost:8080)
- `ABI_ROOT` - ABI directory (default: contracts)
- `ADDRESSES_JSON` - Fallback config file (default: addresses.json)
- `CORS_ORIGINS` - CORS origins (default: empty)

## Production Tips

1. **Secure private keys**: Use Docker secrets, not .env
2. **Enable HTTPS**: Use reverse proxy (Caddy, Traefik)
3. **Set resource limits**: Add to docker-compose.yml
4. **Enable logging**: Configure log rotation
5. **Monitor health**: Set up health check alerts

## Getting Contract Addresses

From deployment artifacts:
```bash
cat /home/lab/repos/robotic_decentralized_organization/blockchain-network/smart-contracts/deployments/1337.json
```

Or from blockchain:
```bash
# If you have the transaction hash
cast tx $TX_HASH --rpc-url http://10.205.10.9:8545
```

## Next Steps

After successful startup:

1. **Fund organization**: Deposit IEC tokens for task rewards
2. **Register services**: Add robot services to the system
3. **Create tasks**: Test task creation and assignment
4. **Monitor operations**: Watch blockchain transactions in real-time

## Support

- **Full docs**: See [README.md](README.md)
- **Check logs**: `./org-web-docker.sh logs`
- **Test connection**: `./org-web-docker.sh test`
- **API docs**: `http://localhost:8080/docs` (when running)
- **Configuration**: `./org-web-docker.sh config`
