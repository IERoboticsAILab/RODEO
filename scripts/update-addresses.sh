#!/bin/bash
# RODEO Address Update Script
# Automatically updates contract addresses across all components after deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if deployment file is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No deployment file specified${NC}"
    echo "Usage: $0 <path-to-deployments.json>"
    echo "Example: $0 blockchain-network/smart-contracts/deployments/1337.json"
    exit 1
fi

DEPLOYMENT_FILE=$1

# Check if deployment file exists
if [ ! -f "$DEPLOYMENT_FILE" ]; then
    echo -e "${RED}Error: Deployment file not found: $DEPLOYMENT_FILE${NC}"
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Warning: jq is not installed. Installing...${NC}"
    sudo apt-get update && sudo apt-get install -y jq
fi

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}RODEO Address Update Script${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Extract addresses from deployment file
echo -e "${YELLOW}Reading deployment addresses...${NC}"
ORG_ADDR=$(jq -r '.contracts.Organization.address' "$DEPLOYMENT_FILE")
TM_ADDR=$(jq -r '.contracts.TaskManager.address' "$DEPLOYMENT_FILE")
SM_ADDR=$(jq -r '.contracts.ServiceManager.address' "$DEPLOYMENT_FILE")
IEC_ADDR=$(jq -r '.contracts.IECoin.address' "$DEPLOYMENT_FILE")

# Validate addresses
if [ "$ORG_ADDR" == "null" ] || [ "$TM_ADDR" == "null" ] || [ "$SM_ADDR" == "null" ] || [ "$IEC_ADDR" == "null" ]; then
    echo -e "${RED}Error: Invalid deployment file format${NC}"
    exit 1
fi

echo -e "  Organization:   ${GREEN}$ORG_ADDR${NC}"
echo -e "  TaskManager:    ${GREEN}$TM_ADDR${NC}"
echo -e "  ServiceManager: ${GREEN}$SM_ADDR${NC}"
echo -e "  IECoin:         ${GREEN}$IEC_ADDR${NC}"
echo ""

# Get repository root (assuming script is in scripts/ directory)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Update Oracle .env
ORACLE_ENV="$REPO_ROOT/oracle/docker/.env"
if [ -f "$ORACLE_ENV" ]; then
    echo -e "${YELLOW}Updating Oracle configuration...${NC}"
    sed -i "s|ORGANIZATION_ADDRESS=.*|ORGANIZATION_ADDRESS=$ORG_ADDR|" "$ORACLE_ENV"
    sed -i "s|TASK_MANAGER_ADDRESS=.*|TASK_MANAGER_ADDRESS=$TM_ADDR|" "$ORACLE_ENV"
    sed -i "s|SERVICE_MANAGER_ADDRESS=.*|SERVICE_MANAGER_ADDRESS=$SM_ADDR|" "$ORACLE_ENV"
    sed -i "s|IECOIN_ADDRESS=.*|IECOIN_ADDRESS=$IEC_ADDR|" "$ORACLE_ENV"
    echo -e "  ${GREEN}✓${NC} $ORACLE_ENV"
else
    echo -e "  ${YELLOW}⚠${NC} Oracle .env not found, skipping"
fi

# Update Org-Web .env
ORGWEB_ENV="$REPO_ROOT/dao-bridge/org-web/.env"
if [ -f "$ORGWEB_ENV" ]; then
    echo -e "${YELLOW}Updating Org-Web configuration...${NC}"
    sed -i "s|ORGANIZATION_ADDRESS=.*|ORGANIZATION_ADDRESS=$ORG_ADDR|" "$ORGWEB_ENV"
    sed -i "s|TASK_MANAGER_ADDRESS=.*|TASK_MANAGER_ADDRESS=$TM_ADDR|" "$ORGWEB_ENV"
    sed -i "s|SERVICE_MANAGER_ADDRESS=.*|SERVICE_MANAGER_ADDRESS=$SM_ADDR|" "$ORGWEB_ENV"
    sed -i "s|IECOIN_ADDRESS=.*|IECOIN_ADDRESS=$IEC_ADDR|" "$ORGWEB_ENV"
    echo -e "  ${GREEN}✓${NC} $ORGWEB_ENV"
else
    echo -e "  ${YELLOW}⚠${NC} Org-Web .env not found, skipping"
fi

# Update ROS-ETH Bridge dao.yaml
BRIDGE_YAML="$REPO_ROOT/dao-bridge/ros-eth-bridge/docker/configs/dao.yaml"
if [ -f "$BRIDGE_YAML" ]; then
    echo -e "${YELLOW}Updating ROS-ETH Bridge configuration...${NC}"
    # Only match contract addresses (starting with 0x), not abi_paths (starting with /)
    sed -i "s|organization: \"0x.*\"|organization: \"$ORG_ADDR\"|" "$BRIDGE_YAML"
    sed -i "s|task_manager: \"0x.*\"|task_manager: \"$TM_ADDR\"|" "$BRIDGE_YAML"
    sed -i "s|service_manager: \"0x.*\"|service_manager: \"$SM_ADDR\"|" "$BRIDGE_YAML"
    sed -i "s|iecoin: \"0x.*\"|iecoin: \"$IEC_ADDR\"|" "$BRIDGE_YAML"
    echo -e "  ${GREEN}✓${NC} $BRIDGE_YAML"
else
    echo -e "  ${YELLOW}⚠${NC} ROS-ETH Bridge dao.yaml not found, skipping"
fi

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}✓ Address update completed!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Restart all Docker containers to apply changes:"
echo "   cd oracle/docker && docker compose restart"
echo "   cd ../../dao-bridge/org-web && docker compose restart"
echo "   cd ../ros-eth-bridge/docker && docker compose restart"
echo ""
echo "2. Verify configurations:"
echo "   docker logs rodeo-oracle | grep -i address"
echo "   docker logs rodeo-org-web | grep -i address"
echo "   docker logs ros-eth-bridge | grep -i chain"
echo ""
