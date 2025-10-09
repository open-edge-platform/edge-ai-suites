# Scenescape Integration Guide

This guide covers the integration of Intel Scenescape with Smart NVR for enhanced traffic monitoring using live data from smart intersection application.

## Overview

Intel Scenescape integration adds advanced traffic analytics to your Smart NVR system, enabling:
- Real-time vehicle counting and tracking
- Traffic flow analysis
- Automated event routing based on vehicle thresholds
- Enhanced surveillance for smart intersection management

## Prerequisites

- **Smart Intersection Application**: The Intel Smart Intersection application must be running and configured on your machine. Follow the setup guide at: https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/get-started.md
- Access to Intel Scenescape traffic analytics platform
- MQTT broker with SSL/TLS support
- Valid Scenescape certificates and credentials

## Environment Variables

### Required Scenescape Configuration

Add these environment variables to enable Scenescape integration:

```bash
# Enable/Disable Scenescape Integration
export NVR_SCENESCAPE=true                    # Set to 'false' to disable

# Scenescape MQTT Configuration
export SCENESCAPE_MQTT_USER="your_username"   # MQTT username
export SCENESCAPE_MQTT_PASSWORD="your_password"  # MQTT password

```

## Installation and Setup

### 1. Install SSL Certificates

**From Smart Intersection Application:**
- Take certificates from: `smart-intersection/src/secrets/certs/`
- Take MQTT username/password from: `smart-intersection/src/secrets/browser.auth`

Place your Scenescape certificates in the `resources/mqtt-certs/` directory:

```bash
cp your-root-cert resources/mqtt-certs/root-cert
cp your-broker-cert resources/mqtt-certs/broker-cert  
cp your-broker-key resources/mqtt-certs/broker-key
```

### 2. Start Scenescape-Enabled Application

```bash
# Set environment and start
export NVR_SCENESCAPE=true
./setup.sh start

# Or restart with new configuration
./setup.sh restart
```

### 3. Verify Integration

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