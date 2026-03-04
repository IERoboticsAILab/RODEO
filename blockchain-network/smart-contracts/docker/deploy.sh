#!/bin/bash
# Smart Contract Deployment Script
# This script deploys smart contracts to Ganache using Docker
#
# Usage: ./deploy.sh [--rebuild|-r]
#   --rebuild, -r: Force rebuild of Docker image

set -e

# Show help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Smart Contract Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --rebuild, -r    Force rebuild of Docker image"
    echo "  --help, -h       Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./deploy.sh                 # Deploy with existing image"
    echo "  ./deploy.sh --rebuild       # Rebuild image and deploy"
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Detect docker-compose command (newer Docker uses "docker compose")
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Error: Neither 'docker-compose' nor 'docker compose' is available"
    echo "   Please install Docker Compose"
    exit 1
fi

echo "═══════════════════════════════════════════════════════"
echo "  Smart Contract Deployment (Docker)"
echo "═══════════════════════════════════════════════════════"
echo ""

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo "❌ Error: .env file not found in smart-contracts folder"
    echo "   Please create a .env file with the required environment variables"
    exit 1
fi

# Check if ganache is running
echo "🔍 Checking if Ganache is running..."
if ! docker ps | grep -q "ganache"; then
    echo "⚠️  Warning: Ganache container is not running"
    echo "   Please start Ganache first:"
    echo "   cd ../ganache-docker && docker compose up -d"
    read -p "   Do you want to continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Test Ganache connectivity
echo "🔗 Testing connection to Ganache..."
if command -v curl &> /dev/null; then
    if curl -s -X POST http://localhost:8545 \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' > /dev/null; then
        echo "   ✅ Ganache is accessible"
    else
        echo "   ⚠️  Warning: Cannot connect to Ganache on localhost:8545"
    fi
fi

cd "$SCRIPT_DIR"

# Check if we should rebuild
REBUILD=false
if [[ "$1" == "--rebuild" ]] || [[ "$1" == "-r" ]]; then
    REBUILD=true
fi

# Check if image exists
IMAGE_EXISTS=false
if docker images | grep -q "smart-contracts.*smart-contract-deployer"; then
    IMAGE_EXISTS=true
fi

if [ "$REBUILD" = true ] || [ "$IMAGE_EXISTS" = false ]; then
    echo ""
    echo "🏗️  Building deployer image..."
    $COMPOSE_CMD build
else
    echo ""
    echo "📦 Using existing image (use --rebuild to force rebuild)"
fi

echo ""
echo "🚀 Deploying smart contracts..."
$COMPOSE_CMD run --rm smart-contract-deployer

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ Deployment complete!"
echo ""
echo "📁 Artifacts saved to: $PROJECT_ROOT/artifacts"
echo "📝 Deployment info:    $PROJECT_ROOT/deployments"
echo "═══════════════════════════════════════════════════════"
