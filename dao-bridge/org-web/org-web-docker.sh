#!/bin/bash
# Helper script for org-web Docker operations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

show_help() {
    cat << EOF
Organization Web Console Docker Helper

Usage: ./org-web-docker.sh [COMMAND]

Commands:
    build       Build the Docker image
    start       Start the container
    stop        Stop the container
    restart     Restart the container
    logs        Show container logs (follow mode)
    status      Show container status
    shell       Open bash shell in container
    clean       Stop and remove container
    rebuild     Clean, rebuild, and start
    test        Test blockchain connection
    config      Show current configuration

Examples:
    ./org-web-docker.sh build
    ./org-web-docker.sh start
    ./org-web-docker.sh logs
    ./org-web-docker.sh test

EOF
}

case "$1" in
    build)
        echo "Building org-web Docker image..."
        docker compose build
        ;;
    start)
        echo "Starting org-web container..."
        docker compose up
        echo "✅ Org-web started at http://localhost:${HOST_PORT:-8080}"
        echo "Use './org-web-docker.sh logs' to view logs"
        ;;
    stop)
        echo "Stopping org-web container..."
        docker compose stop
        ;;
    restart)
        echo "Restarting org-web container..."
        docker compose restart
        ;;
    logs)
        echo "Following org-web logs (Ctrl+C to exit)..."
        docker compose logs -f org-web
        ;;
    shell)
        echo "Opening shell in org-web container..."
        docker exec -it org-web-console bash
        ;;
    status)
        echo "Org-web container status:"
        docker compose ps
        echo ""
        echo "Health check:"
        docker inspect org-web-console --format='{{.State.Health.Status}}' 2>/dev/null || echo "Container not running"
        ;;
    clean)
        echo "Cleaning up org-web container..."
        docker compose down
        ;;
    rebuild)
        echo "Rebuilding org-web (clean, build, start)..."
        docker compose down
        docker compose build --no-cache
        docker compose up -d
        echo "✅ Org-web rebuilt and started"
        ;;
    test)
        echo "Testing blockchain connection..."
        if [ -f .env ]; then
            source .env
            echo "RPC URL: $RPC_URL"
            docker exec org-web-console python3 -c "
from backend.org_code import web3, RPC_URL, ORG_CONTRACT_ADDR, IECOIN_ADDR
print(f'Connected: {web3.is_connected()}')
print(f'Block number: {web3.eth.block_number}')
print(f'Organization: {ORG_CONTRACT_ADDR}')
print(f'IECoin: {IECOIN_ADDR}')
" 2>/dev/null || echo "❌ Container not running or backend error"
        else
            echo "❌ .env file not found"
        fi
        ;;
    config)
        echo "Current configuration:"
        if [ -f .env ]; then
            grep -v "PRIVATE" .env | grep -v "^#" | grep -v "^$"
        else
            echo "❌ .env file not found"
        fi
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
