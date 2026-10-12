#!/bin/bash

#################
# Script to generate an offline package for Metro Vision AI applications.
# This package can be copied to another device or DDIL environment.
#
# Usage: ./offline-package-generator.sh
# Example: ./offline-package-generator.sh
#
#################

set -e  # Exit on any error

echo "Starting offline package generation..."

# Copy Docker compose file and .env file and update it
echo "Copying Docker compose and .env files..."
cp ../.env ./
cp ../compose-without-scenescape.yml ./docker-compose.yml

# Update .env file to set SAMPLE_APP=loitering-detection and HOST_IP=127.0.0.1
echo "Updating .env file..."
sed -i 's/^SAMPLE_APP=.*/SAMPLE_APP=loitering-detection/' .env
sed -i 's/^HOST_IP=.*/HOST_IP=127.0.0.1/' .env

# This app's MQTT topic prefixes are not part of the shared .env (they're
# loitering-detection-specific); set them here, idempotently, in a clearly
# commented section of this script's own local .env copy.
sed -i \
  -e '/^# loitering-detection: MQTT topic prefixes/d' \
  -e '/^# SOURCE_TOPIC_PREFIX -/d' \
  -e '/^#   publishes to/d' \
  -e '/^# DEST_TOPIC_PREFIX -/d' \
  -e '/^#   to for the Grafana/d' \
  -e '/^SOURCE_TOPIC_PREFIX=/d' \
  -e '/^DEST_TOPIC_PREFIX=/d' \
  .env
cat >> .env <<'EOF'

# loitering-detection: MQTT topic prefixes used by the mqtt-table-flattener sidecar.
# SOURCE_TOPIC_PREFIX - prefix of the raw per-frame metadata topic gvametaconvert
#   publishes to (<prefix>/<stream-id>); must match sample_start.sh's launch topics.
# DEST_TOPIC_PREFIX - prefix the flattener republishes one-row-per-object summaries
#   to for the Grafana MQTT table panel (<prefix>/<stream-id>).
SOURCE_TOPIC_PREFIX=object_tracking
DEST_TOPIC_PREFIX=loiter_status
EOF

# Update docker-compose.yml file
# Remove "${SAMPLE_APP}/" from all image paths in docker-compose.yml
echo "Updating docker-compose.yml file..."
sed -i 's#${SAMPLE_APP}/##g' docker-compose.yml
sed -i "s/\${DLSTREAMER_PIPELINE_SERVER_IMAGE}/$(grep "DLSTREAMER_PIPELINE_SERVER_IMAGE" .env | cut -d'=' -f2 | sed 's/\//\\\//g')/g" docker-compose.yml

# This app no longer uses Node-RED (zone/dwell logic now runs in gvaanalytics); strip it here too
# since this script keeps its own local docker-compose.yml copy.
awk '
    /^  node-red:/ { skip=1; next }
    skip && /^  [^ ]/ { skip=0 }
    skip && /^[^ ]/ { skip=0 }
    !skip { print }
  ' docker-compose.yml > docker-compose.yml.tmp && mv docker-compose.yml.tmp docker-compose.yml
sed -i '/^      - node-red$/d' docker-compose.yml
sed -i '/^  node-red-node-modules:$/d' docker-compose.yml

# Add the mqtt-table-flattener service (reshapes object_tracking/<N> into
# loiter_status/<N> rows for the Grafana table); path has no ${SAMPLE_APP}/
# prefix since this script flattens that prefix out of its local copy above.
# Reuses the dlstreamer-pipeline-server image (already pulled, already has
# paho-mqtt) instead of adding a new one; values read from the local .env
# copy, same as the DLSTREAMER_PIPELINE_SERVER_IMAGE substitution above.
if ! grep -q '^  mqtt-table-flattener:' docker-compose.yml; then
  DLSPS_IMAGE=$(grep "^DLSTREAMER_PIPELINE_SERVER_IMAGE=" .env | cut -d'=' -f2)
  SRC_TOPIC_PREFIX=$(grep "^SOURCE_TOPIC_PREFIX=" .env | cut -d'=' -f2)
  DST_TOPIC_PREFIX=$(grep "^DEST_TOPIC_PREFIX=" .env | cut -d'=' -f2)
  awk -v image="$DLSPS_IMAGE" -v src_prefix="$SRC_TOPIC_PREFIX" -v dst_prefix="$DST_TOPIC_PREFIX" '
    /^networks:/ && !inserted {
      print "  mqtt-table-flattener:"
      print "    image: " image
      print "    container_name: mqtt-table-flattener"
      print "    environment:"
      print "      - MQTT_HOST=broker"
      print "      - MQTT_PORT=1883"
      print "      - SOURCE_TOPIC_PREFIX=" src_prefix
      print "      - DEST_TOPIC_PREFIX=" dst_prefix
      print "    volumes:"
      print "      - \"./src/mqtt-table-flattener:/app:ro\""
      print "    entrypoint: [\"python3\", \"/app/flatten.py\"]"
      print "    depends_on:"
      print "      - broker"
      print "    networks:"
      print "      - app_network"
      print "    restart: on-failure:5"
      print ""
      inserted=1
    }
    { print }
  ' docker-compose.yml > docker-compose.yml.tmp && mv docker-compose.yml.tmp docker-compose.yml
fi

# Run install.sh to download all required models and videos
echo "Running install.sh to download models and videos..."
./install.sh 127.0.0.1

# Run docker compose to pull all the images and download the grafana plugins
mkdir -p ./src/grafana/plugins
chown -R "$(id -u):$(id -g)" ./src/grafana/plugins 2>/dev/null || true

echo "Pulling Docker images and downloading Grafana plugins..."
docker compose up -d
echo "Waiting for services to be healthy..."
sleep 60

docker cp $(docker ps -q --filter "name=grafana"):/var/lib/grafana/plugins ./src/grafana/plugins

docker compose down

sed -i '/datasources\.yml.*datasources\.yml/a\      - "./src/grafana/plugins:/var/lib/grafana/plugins"' docker-compose.yml
sed -i '/GF_INSTALL_PLUGINS=grafana-mqtt-datasource/d' docker-compose.yml
sed -i '/container_name: dlstreamer-pipeline-server/a\    extra_hosts:\n      - "stun.l.google.com:127.0.0.1"' docker-compose.yml


# Create directory offline-package and copy all the files into it
echo "Creating offline-package directory and copying files..."
mkdir -p offline-package

tar --exclude='./offline-package' -cf - . | (cd offline-package && tar -xf -)

# Create a new directory inside it called docker-images and save all the docker images available in docker compose .yml file
echo "Creating docker-images directory and saving Docker images..."
mkdir -p offline-package/docker-images

# Extract images from docker-compose.yml and save them
docker compose config | grep -E "^\s+image:" | sed 's/.*image: //' | sort -u | while read image; do
  echo "Saving Docker image: $image"
  filename=$(echo "$image" | sed 's/[\/:]/-/g')
  docker pull "$image"
  docker save "$image" | gzip > "offline-package/docker-images/${filename}.tar.gz"
  echo "Saved: ${filename}.tar.gz"
done

# Create load-images.sh script in offline-package directory
echo "Creating load-images.sh script..."
cat > offline-package/load-images.sh << 'EOF'
#!/bin/bash

#################
# Advanced script to load Docker images from the offline package
# This script loads all Docker images from the docker-images directory with progress tracking
#
# Usage: ./load-docker-images.sh
# Example: ./load-docker-images.sh
#
#################

set -e  # Exit on any error

echo "Starting offline package generation..."

# Check if Docker is available and running
echo "Checking Docker availability..."
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH!"
    echo "Please install Docker and try again."
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running!"
    echo "Please start Docker daemon and try again."
    exit 1
fi

echo "✓ Docker is available and running"

# Check if docker compose is available
if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not available!"
    echo "Please install Docker Compose and try again."
    exit 1
fi

echo "✓ Docker Compose is available"

echo "Starting Docker images loading..."

# Check if docker-images directory exists
if [ ! -d "docker-images" ]; then
    echo "Error: docker-images directory not found!"
    echo "Please make sure you're running this script from the offline-package directory."
    exit 1
fi

# Count total files
total_files=$(find docker-images -name "*.tar.gz" | wc -l)
if [ "$total_files" -eq 0 ]; then
    echo "Error: No .tar.gz files found in docker-images directory!"
    exit 1
fi

echo "Found $total_files Docker image files to load..."

# Load all Docker images from docker-images directory
current_file=0
failed_loads=0

for image_file in docker-images/*.tar.gz; do
    if [ -f "$image_file" ]; then
        current_file=$((current_file + 1))
        echo "[$current_file/$total_files] Loading Docker image: $(basename "$image_file")"
        
        if docker load < <(gunzip -c "$image_file"); then
            echo "✓ Successfully loaded: $(basename "$image_file")"
        else
            echo "✗ Failed to load: $(basename "$image_file")"
            failed_loads=$((failed_loads + 1))
        fi
        echo "---"
    fi
done

# Summary
echo "Docker images loading completed!"
echo "Successfully loaded: $((total_files - failed_loads))/$total_files images"

if [ "$failed_loads" -gt 0 ]; then
    echo "Failed to load: $failed_loads images"
    exit 1
fi

# Show loaded images
echo "Verifying loaded images..."
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"

EOF

# Make the script executable
chmod +x offline-package/load-images.sh
echo "load-images.sh script created and made executable."


echo "Offline package generation completed successfully!"
echo "Package location: ./offline-package"
