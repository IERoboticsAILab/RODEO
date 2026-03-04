#!/bin/bash
# Robot Emulator Docker Control Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect docker-compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Error: Neither 'docker-compose' nor 'docker compose' is available"
    exit 1
fi

# Show help
show_help() {
    cat << EOF
Robot Emulator Docker Control Script

Usage: ./robot-emulator.sh [COMMAND]

Commands:
  build     Build the Docker image
  start     Start the robot emulator
  stop      Stop the robot emulator
  restart   Restart the robot emulator
  logs      View logs (follow mode)
  status    Check if container is running
  shell     Open interactive shell in container
  help      Show this help message

Examples:
  ./robot-emulator.sh build
  ./robot-emulator.sh start
  ./robot-emulator.sh logs
EOF
}

case "${1:-help}" in
    build)
        echo "🏗️  Building robot emulator image..."
        $COMPOSE_CMD build
        echo "✅ Build complete!"
        ;;
    
    start)
        echo "🚀 Starting robot emulator..."
        $COMPOSE_CMD up -d
        echo "✅ Robot emulator started!"
        echo ""
        echo "📋 The robot will:"
        echo "   1. Register a delivery service"
        echo "   2. Wait for task assignments"
        echo "   3. Execute tasks automatically"
        echo "   4. Submit proofs"
        echo ""
        echo "View logs: ./robot-emulator.sh logs"
        ;;
    
    stop)
        echo "🛑 Stopping robot emulator..."
        $COMPOSE_CMD down
        echo "✅ Robot emulator stopped!"
        ;;
    
    restart)
        echo "🔄 Restarting robot emulator..."
        $COMPOSE_CMD restart
        echo "✅ Robot emulator restarted!"
        ;;
    
    logs)
        echo "📋 Showing robot emulator logs (Ctrl+C to exit)..."
        $COMPOSE_CMD logs -f robot-emulator
        ;;
    
    status)
        if docker ps | grep -q "robot-emulator-demo"; then
            echo "✅ Robot emulator is running"
            docker ps --filter "name=robot-emulator-demo" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        else
            echo "❌ Robot emulator is not running"
        fi
        ;;
    
    shell)
        echo "🐚 Opening shell in robot emulator container..."
        docker exec -it robot-emulator-demo bash
        ;;
    
    help|--help|-h)
        show_help
        ;;
    
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
