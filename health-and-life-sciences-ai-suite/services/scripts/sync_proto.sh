#!/bin/bash
# ============================================================================
# Proto Sync Script
# ============================================================================
# Syncs vital.proto from aggregator-service to all other services
#
# Usage:
#   ./scripts/sync-proto.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Source proto file
PROTO_SOURCE="services/aggregator-service/proto/vital.proto"

# Target services
SERVICES=(
    "mdpnp-service"
    "rppg-service"
    # Add other services as they're created
)

echo "=========================================="
echo "Proto File Sync Utility"
echo "=========================================="
echo ""

# Check source exists
if [ ! -f "$PROTO_SOURCE" ]; then
    echo -e "${RED}ERROR: Source proto not found: $PROTO_SOURCE${NC}"
    exit 1
fi

echo -e "Source: ${GREEN}$PROTO_SOURCE${NC}"
echo ""

# Sync to each service
for SERVICE in "${SERVICES[@]}"; do
    SERVICE_DIR="services/$SERVICE"
    DEST="$SERVICE_DIR/proto/vital.proto"
    
    if [ ! -d "$SERVICE_DIR" ]; then
        echo -e "${YELLOW}⚠  Skipping $SERVICE (directory not found)${NC}"
        continue
    fi
    
    # Create proto directory if it doesn't exist
    mkdir -p "$SERVICE_DIR/proto"
    
    # Copy proto file
    cp "$PROTO_SOURCE" "$DEST"
    
    echo -e "${GREEN}✓${NC} Copied to $SERVICE"
done

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Proto sync complete!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff services/*/proto/vital.proto"
echo "  2. Rebuild services: docker-compose build"
echo "  3. Commit: git add services/*/proto/vital.proto"
echo ""