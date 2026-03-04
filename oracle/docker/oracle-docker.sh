#!/bin/bash
# Helper script for Oracle Docker operations

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

show_help() {
    cat << EOF
Oracle Docker Helper Script

Usage: ./oracle-docker.sh [COMMAND]

Commands:
    build       Build the Docker image
    start       Start the oracle container
    stop        Stop the oracle container
    restart     Restart the oracle container
    logs        Show container logs (follow mode)
    attach      Attach to the running container (interactive)
    exec        Execute a command in the container
    status      Show container status
    clean       Stop and remove the container
    rebuild     Clean, rebuild, and start

Examples:
    ./oracle-docker.sh build
    ./oracle-docker.sh start
    ./oracle-docker.sh logs
    ./oracle-docker.sh attach

EOF
}

case "$1" in
    build)
        echo "Building oracle Docker image..."
        docker compose build
        ;;
    start)
        echo "Starting oracle container..."
        docker compose up
        echo "Oracle started. Use './oracle-docker.sh logs' to view logs"
        echo "or './oracle-docker.sh attach' for interactive menu"
        ;;
    stop)
        echo "Stopping oracle container..."
        docker compose stop
        ;;
    restart)
        echo "Restarting oracle container..."
        docker compose restart
        ;;
    logs)
        echo "Following oracle logs (Ctrl+C to exit)..."
        docker compose logs -f oracle
        ;;
    attach)
        echo "Attaching to oracle container (Ctrl+P Ctrl+Q to detach)..."
        docker attach rodeo-oracle
        ;;
    exec)
        shift
        if [ -z "$1" ]; then
            echo "Entering oracle container shell..."
            docker exec -it rodeo-oracle bash
        else
            echo "Executing: $@"
            docker exec -it rodeo-oracle "$@"
        fi
        ;;
    status)
        echo "Oracle container status:"
        docker compose ps
        ;;
    clean)
        echo "Cleaning up oracle container..."
        docker compose down
        ;;
    rebuild)
        echo "Rebuilding oracle (clean, build, start)..."
        docker compose down
        docker compose build --no-cache
        docker compose up -d
        echo "Oracle rebuilt and started"
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
