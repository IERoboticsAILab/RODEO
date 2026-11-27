#!/bin/bash
# RODEO demo without a robot: agent + fake executor.
set -e
cd "$(dirname "$0")"
case "${1:-help}" in
  build)  docker compose build ;;
  start)  docker compose up -d && echo "Started. Follow with: ./demo.sh logs" ;;
  stop)   docker compose stop -t 30 && echo "Stopped (the agent deactivated its service)." ;;
  down)   docker compose down -t 30 ;;
  logs)   docker compose logs -f ;;
  status) docker compose ps ;;
  *)
    cat <<USAGE
Usage: ./demo.sh build | start | stop | down | logs | status

  build   build the agent image (first time, or after code changes)
  start   start the agent and the fake executor
  logs    follow both logs
  stop    stop both; the agent deactivates its service first
  down    stop and remove the containers
USAGE
    ;;
esac
