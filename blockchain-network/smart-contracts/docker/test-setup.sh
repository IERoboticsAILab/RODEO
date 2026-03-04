#!/bin/bash
# Quick test script to verify the Docker deployment setup

set -e

echo "🧪 Testing Smart Contract Docker Deployment Setup"
echo "=================================================="
echo ""

# Check Docker
echo "1. Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "   ❌ Docker is not installed"
    exit 1
fi
echo "   ✅ Docker is installed"

# Check Docker Compose
echo "2. Checking Docker Compose..."
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
    echo "   ✅ Docker Compose is available (docker-compose)"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
    echo "   ✅ Docker Compose is available (docker compose)"
else
    echo "   ❌ Docker Compose is not installed"
    exit 1
fi

# Check .env file
echo "3. Checking .env configuration..."
if [ ! -f "../.env" ]; then
    echo "   ❌ .env file not found in smart-contracts directory"
    echo "   Please create one with necessary environment variables"
    exit 1
fi
echo "   ✅ .env file exists"

# Check if required variables are in .env
MISSING_VARS=""
for VAR in GANACHE_URL PRIVATE_KEY_DEPLOYER PRIVATE_KEY_ORGANIZATION PRIVATE_KEY_ORACLE; do
    if ! grep -q "^$VAR=" "../.env"; then
        MISSING_VARS="$MISSING_VARS $VAR"
    fi
done

if [ -n "$MISSING_VARS" ]; then
    echo "   ⚠️  Missing environment variables:$MISSING_VARS"
else
    echo "   ✅ Required environment variables are present"
fi

# Check contracts directory
echo "4. Checking contracts directory..."
if [ ! -d "../contracts" ] || [ -z "$(ls -A ../contracts/*.sol 2>/dev/null)" ]; then
    echo "   ❌ No Solidity contracts found"
    exit 1
fi
CONTRACT_COUNT=$(find ../contracts -name "*.sol" -type f | wc -l)
echo "   ✅ Found $CONTRACT_COUNT Solidity contract(s)"

# Check if Ganache is running
echo "5. Checking Ganache availability..."
if docker ps | grep -q "ganache"; then
    echo "   ✅ Ganache container is running"
    GANACHE_RUNNING=true
else
    echo "   ⚠️  Ganache container is not running"
    echo "   You can start it with: cd ../ganache-docker && docker-compose up -d"
    GANACHE_RUNNING=false
fi

# Test Docker build
echo "6. Testing Docker image build..."
if $COMPOSE_CMD build 2>&1 | grep -q "ERROR"; then
    echo "   ❌ Docker build failed"
    exit 1
fi
echo "   ✅ Docker image builds successfully"

echo ""
echo "=================================================="
echo "✅ All checks passed!"
echo ""
if [ "$GANACHE_RUNNING" = false ]; then
    echo "⚠️  Note: Ganache is not running. Start it before deploying."
fi
echo ""
echo "Ready to deploy! Run: ./deploy.sh"
echo "=================================================="
