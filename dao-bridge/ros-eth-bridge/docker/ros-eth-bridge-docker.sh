#!/bin/bash
# Helper script for ROS-ETH Bridge Docker operations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

show_help() {
    cat << EOF
ROS-ETH Bridge Docker Helper

Usage: ./ros-eth-bridge-docker.sh [COMMAND]

Commands:
    build       Build the Docker image
    start       Start the bridge container
    stop        Stop the bridge container
    restart     Restart the bridge container
    logs        Show container logs (follow mode)  
    shell       Open bash shell in container
    status      Show container status
    rosnode     Show ROS node info
    rostopic    List ROS topics
    clean       Stop and remove container
    rebuild     Clean, rebuild, and start
    check       Check configuration and dependencies

Examples:
    ./ros-eth-bridge-docker.sh build
    ./ros-eth-bridge-docker.sh start
    ./ros-eth-bridge-docker.sh logs
    ./ros-eth-bridge-docker.sh rostopic

EOF
}

check_config() {
    echo "Checking configuration..."
    
    # Check if dao.yaml exists
    if [ ! -f "configs/dao.yaml" ]; then
        echo "❌ configs/dao.yaml not found"
        echo "   Copy from template: cp configs/dao.yaml.template configs/dao.yaml"
        return 1
    else
        echo "✅ dao.yaml found"
    fi
    
    # Check if wallet exists (expand tilde)
    if [ -f .env ]; then
        source .env
        WALLET_EXPANDED="${WALLET_PATH/#\~/$HOME}"
        if [ ! -f "$WALLET_EXPANDED" ]; then
            echo "❌ Wallet file not found: $WALLET_EXPANDED"
            echo "   Create wallet using: python3 configs/make_wallet.py"
            return 1
        else
            echo "✅ Wallet found at $WALLET_EXPANDED"
        fi
    else
        echo "⚠️  .env file not found, using defaults"
    fi
    
    # Check if ROS Master is running
    if [ -f .env ]; then
        source .env
    fi
    ROS_MASTER_URI=${ROS_MASTER_URI:-http://localhost:11311}
    
    if timeout 2 bash -c "curl -s $ROS_MASTER_URI" > /dev/null 2>&1; then
        echo "✅ ROS Master accessible at $ROS_MASTER_URI"
    else
        echo "⚠️  ROS Master not accessible at $ROS_MASTER_URI"
        echo "   Start roscore before running the bridge"
    fi
    
    echo ""
    echo "Configuration check complete"
}

case "$1" in
    build)
        echo "Building ROS-ETH Bridge Docker image..."
        docker compose build
        ;;
    start)
        echo "Starting ROS-ETH Bridge container..."
        check_config
        echo ""
        docker compose up
        echo "✅ Bridge started"
        echo "Use './ros-eth-bridge-docker.sh logs' to view logs"
        ;;
    stop)
        echo "Stopping ROS-ETH Bridge container..."
        docker compose stop
        ;;
    restart)
        echo "Restarting ROS-ETH Bridge container..."
        docker compose restart
        ;;
    logs)
        echo "Following bridge logs (Ctrl+C to exit)..."
        docker compose logs -f ros-eth-bridge
        ;;
    shell)
        echo "Opening shell in ROS-ETH Bridge container..."
        docker exec -it ros-eth-bridge bash
        ;;
    status)
        echo "ROS-ETH Bridge container status:"
        docker compose ps
        echo ""
        echo "Health check:"
        docker inspect ros-eth-bridge --format='{{.State.Health.Status}}' 2>/dev/null || echo "Container not running"
        ;;
    rosnode)
        echo "ROS nodes in bridge container:"
        docker exec ros-eth-bridge bash -lc "rosnode list" 2>/dev/null || echo "❌ Container not running or ROS not ready"
        ;;
    rostopic)
        echo "ROS topics from bridge:"
        docker exec ros-eth-bridge bash -lc "rostopic list | grep dao" 2>/dev/null || echo "❌ Container not running or ROS not ready"
        ;;
    clean)
        echo "Cleaning up ROS-ETH Bridge container..."
        docker compose down
        ;;
    rebuild)
        echo "Rebuilding ROS-ETH Bridge (clean, build, start)..."
        docker compose down
        docker compose build --no-cache
        docker compose up -d
        echo "✅ Bridge rebuilt and started"
        ;;
    check)
        check_config
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        if [ -z "$1" ]; then
            show_help
        else
            echo "Unknown command: $1"
            echo ""
            show_help
            exit 1
        fi
        ;;
esac
