# Scenescape Integration Guide

This guide covers the integration of Intel Scenescape with Smart NVR for enhanced traffic monitoring using live data from smart intersection application.

## Overview

Intel Scenescape integration adds advanced traffic analytics to your Smart NVR system, enabling:
- Real-time vehicle counting and tracking
- Traffic flow analysis
- Automated event routing based on vehicle thresholds
- Enhanced surveillance for smart intersection management

## Prerequisites

- **Smart Intersection Application**: The Intel Smart Intersection application must be running and configured on your machine. Follow the [Smart Intersection User Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/get-started.md).
- Access to Intel Scenescape traffic analytics platform
- MQTT broker with SSL/TLS support
- Valid Scenescape certificates and credentials

## Installation and Setup

### Step 1: Obtain Certificates and Credentials from Smart Intersection

**Prerequisites:** First, ensure Smart Intersection application is running following the setup guide.

**1.1 Locate Certificate Files:**
```bash
# Navigate to Smart Intersection secrets directory  
cd /path/to/smart-intersection/src/secrets/

# Check certificate files structure - you should see:
ls -la certs/
# Expected files:
# scenescape-ca.pem       (root certificate)
# scenescape-broker.crt   (broker certificate) 
# scenescape-broker.key   (broker private key)
```

**1.2 Get MQTT Credentials:**
```bash
# Check browser.auth file for MQTT credentials
cat secrets/browser.auth
# Expected JSON format:
# {"user": "<user>", "password": "<password>"}
```

### Step 2: Configure Environment Variables

Using the credentials obtained from Step 1, set these environment variables:

```bash
# Enable Scenescape Integration
export NVR_SCENESCAPE=true

# MQTT Configuration (from browser.auth JSON file)
export SCENESCAPE_MQTT_USER="<user>"                    # "user" field from JSON
export SCENESCAPE_MQTT_PASSWORD="<password>"       # "password" field from JSON

```

### Step 3: Install SSL Certificates

Copy the certificates obtained in Step 1 to Smart NVR:

```bash
# From Smart Intersection directory, copy certificates to Smart NVR
# Adjust paths according to your installation directories

cp /path/to/smart-intersection/src/secrets/certs/scenescape-ca.pem \
   /path/to/smart-nvr/resources/mqtt-certs/root-cert

cp /path/to/smart-intersection/src/secrets/certs/scenescape-broker.crt \
   /path/to/smart-nvr/resources/mqtt-certs/broker-cert

cp /path/to/smart-intersection/src/secrets/certs/scenescape-broker.key \
   /path/to/smart-nvr/resources/mqtt-certs/broker-key

# Verify certificates are installed correctly
ls -la /path/to/smart-nvr/resources/mqtt-certs/
```

### Step 4: Start Scenescape-Enabled Application

```bash
# Start the application 
./setup.sh start

# Or restart with new configuration
./setup.sh restart
```

### Step 5: Verify Integration

Check logs to confirm Scenescape connection:

```bash
docker logs nvr-event-router -f
# Look for: "Scenescape MQTT client started"
```

## User Interface Changes

### With Scenescape Enabled and Scenescape Source Selected

![Scenescape Enabled Interface](_images/Scenescape_enabled.png)

When Scenescape is enabled (`NVR_SCENESCAPE=true`) and scenescape source is selected:
- Source dropdown shows both **"frigate"** and **"scenescape"** options
- **Vehicle Count** field becomes visible and editable
- Users can set minimum vehicle threshold for rule triggering (e.g., 5, 10, 15)
- Rules table includes "Vehicle Count" column for tracking thresholds
- Vehicle count validation ensures non-negative integers only

### With Scenescape Enabled but Frigate Source Selected

![Frigate Selected Interface](_images/Scenescape_enabled_frigate.png)

When Scenescape is enabled but frigate source is selected:
- Source dropdown still shows both **"frigate"** and **"scenescape"** options  
- **Vehicle Count** field is automatically hidden (not applicable for frigate)
- Standard frigate rule configuration with detection labels
- Rules table shows "Vehicle Count" column but displays "-" for frigate rules
- Full frigate functionality remains available

### With Scenescape Completely Disabled (`NVR_SCENESCAPE=false`)

![Scenescape Disabled Interface](_images/Scenescape_disabled.png)

When Scenescape is disabled in environment variables:
- Source dropdown shows **only** "frigate" option
- Vehicle Count field is never visible
- Rules table **excludes** the "Vehicle Count" column entirely  
- Pure frigate-only functionality and interface
- Scenescape MQTT client will not start

## Auto-Route Events Configuration

### Creating Rules

**Steps (both sources):**
1. Navigate to **Auto-Route Events** tab
2. **Select Source:** "scenescape" or "frigate"
3. **Set Vehicle Count:** (Scenescape only) Define minimum threshold (e.g., 5)
4. **Select Camera:** Choose target camera 
5. **Choose Detection Label:** Select object type
6. **Select Action:** "Summarize" or "Add to Search"
7. **Click Add Rule**

**Key Differences:**
- **Scenescape:** Vehicle Count field visible when selected
- **Frigate:** Vehicle Count field hidden

### Rule Behavior Examples

**Scenescape Rule Example:**
```
Source: scenescape
Camera: backyard
Vehicle Count: 5
Label: vehicle
Action: Summarize
```
*Triggers video summarization when 5+ vehicles detected in backyard camera*

**Frigate Rule Example:**
```
Source: frigate
Camera: livingroom
Label: person
Action: Add to Search  
```
*Adds person detection events to search index for livingroom camera*

## Troubleshooting

### Common Issues

**Scenescape features not visible:**
```bash
# Check and set environment variable
echo $NVR_SCENESCAPE  # Should show 'true'
export NVR_SCENESCAPE=true
./setup.sh restart
# Refresh browser (Ctrl+F5)
```

**No scenescape events received:**
```bash
# Check MQTT connection
docker logs nvr-event-router | grep -i scenescape
```

### Debug Commands

```bash
# Check environment variables
env | grep NVR_SCENESCAPE
env | grep SCENESCAPE

# Monitor MQTT messages
docker logs nvr-event-router -f | grep "scenescape"

# Check UI logs
docker logs nvr-event-router-ui -f

# Verify Scenescape MQTT connection
docker logs nvr-event-router | grep "Scenescape MQTT client"
```

## Support

For Scenescape integration issues:
1. Verify environment variables are properly set
2. Check that Scenescape/Smart intersection application is running
3. Ensure MQTT broker is accessible and certificates are valid
4. Review logs using debug commands above
5. Contact support with relevant log excerpts

For general Smart NVR issues, see the [main documentation](get-started.md).

---

*Last updated: October 2025*
