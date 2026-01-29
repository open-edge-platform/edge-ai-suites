
# Configuration to connect to secure External MQTT broker

This guide explains how to securely connect your application to an external MQTT broker using
TLS/SSL encryption for both data ingestion and alert publishing, replacing the default built-in
MQTT broker.

## Step 1: Generate TLS Certificates

Follow the below steps to generate the required certificates:

```bash
# Navigate to the application directory
cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series

# Load environment variables
source ./.env

# Create and clean the certificates directory
mkdir -p certs
sudo rm -rf ./certs/*
cd certs

# Set your external MQTT broker hostname/IP
# Replace <YOUR_MQTT_BROKER_IP> with your actual MQTT broker IP or hostname
EXTERNAL_MQTT_BROKER_HOST=<YOUR_MQTT_BROKER_IP>
```

### Generate CA Certificate

```bash
# Generate CA private key (3072-bit for better security)
openssl genrsa -out ca.key 3072

# Generate CA certificate
openssl req -new -x509 -days 365 -key ca.key -out ca_cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=MQTT-CA"

# Create a copy with the expected filename
cp ca_cert.pem ca_certificate.pem
```

### Generate Server Certificate

```bash
# Generate server private key
openssl genrsa -out server.key 3072

# Generate server certificate signing request
openssl req -new -key server.key -out server.csr \
  -subj "/C=US/ST=State/L=City/O=Organization/OU=OrgUnit/CN=$EXTERNAL_MQTT_BROKER_HOST"

# Create extensions file for Subject Alternative Names
cat > server.ext << EOF
[v3_req]
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = $EXTERNAL_MQTT_BROKER_HOST
DNS.2 = localhost
IP.1 = 127.0.0.1
EOF

# Generate server certificate
openssl x509 -req -in server.csr -CA ca_certificate.pem -CAkey ca.key \
  -CAcreateserial -out server_certificate.pem -days 365 \
  -extensions v3_req -extfile server.ext

# Set proper ownership
sudo chown $TIMESERIES_UID:$TIMESERIES_UID ca_certificate.pem
cd ..
```

## Step 2: Configure Docker Services

Make the below changes to the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml` file.

### Update docker-compose.yml

Add the CA certificate volume mount to the following services in your `docker-compose.yml`:

```yaml
ia-telegraf:
  volumes:
    # ... existing volumes ...
    - ./certs/ca_certificate.pem:/run/secrets/ca_certificate.pem:ro

ia-time-series-analytics-microservice:
  volumes:
    # ... existing volumes ...
    - ./certs/ca_certificate.pem:/run/secrets/ca_certificate.pem:ro

ia-mqtt-publisher:
  volumes:
    # ... existing volumes ...
    - ./certs/ca_certificate.pem:/run/secrets/ca_certificate.pem:ro
```

### Remove default built-in MQTT Broker Dependencies

Remove or comment out the default built-in MQTT broker dependency:

```yaml
ia-time-series-analytics-microservice:
  depends_on:
    - ia-influxdb
    # - ia-mqtt-broker  # Comment this out

ia-telegraf:
  depends_on:
    - ia-influxdb
    # - ia-mqtt-broker  # Comment this out
```

### Update Network Configuration

Replace `ia-mqtt-broker` with your external broker's hostname/IP in the proxy settings:

```yaml
ia-telegraf:
  environment:
    no_proxy: "ia-influxdb,<YOUR_MQTT_BROKER_IP>,ia-opcua-server,ia-time-series-analytics-microservice,${no_proxy}"
    NO_PROXY: "ia-influxdb,<YOUR_MQTT_BROKER_IP>,ia-opcua-server,ia-time-series-analytics-microservice,${no_proxy}"

ia-time-series-analytics-microservice:
  environment:
    no_proxy: "ia-influxdb,<YOUR_MQTT_BROKER_IP>,ia-opcua-server,localhost,${no_proxy}"
    NO_PROXY: "ia-influxdb,<YOUR_MQTT_BROKER_IP>,ia-opcua-server,localhost,${no_proxy}"
```

### Configure MQTT Publisher Port

Add the `PORT` and `SECURE_MODE` environment variables to the `ia-mqtt-publisher` service.
Replace the `<YOUR_MQTT_BROKER_IP>` with your external broker's hostname/IP and `<MQTT_PORT>` with your broker's TLS/SSL port.
Set `SECURE_MODE` to `true` to use TLS/SSL.

```yaml
ia-mqtt-publisher:
  environment:
    AppName: "mqtt-publisher"
    HOST_IP: <YOUR_MQTT_BROKER_IP>
    PORT: <MQTT_PORT>
    SECURE_MODE: true
    # ... other environment variables ...
```

## Step 3: Configure Application Settings

### 3.1 Update Telegraf Configuration

Edit your Telegraf configuration file:
`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/<sample_app>/telegraf-config/Telegraf.conf`

```toml
[[inputs.mqtt_consumer]]
  ## MQTT broker URLs - use ssl:// for secure connection
  servers = ["ssl://<YOUR_MQTT_BROKER_IP>:<MQTT_PORT>"]

  ## TLS Configuration
  tls_ca = "/run/secrets/ca_certificate.pem"

```

**Replace:**
- `<YOUR_MQTT_BROKER_IP>` with your broker's IP or hostname
- `<MQTT_PORT>` with your broker's TLS port

### 3.2 Update Kapacitor Configuration

You need to edit and volume mount `/path/to/edge-ai-libraries/microservices/time-series-analytics/config/kapacitor.conf` file.
Edit the `kapacitor.conf` file:

```toml
[[mqtt]]
  enabled = true
  name = "my_mqtt_broker"
  default = true

  # Use SSL connection
  url = "ssl://<YOUR_MQTT_BROKER_IP>:<MQTT_PORT>"

  # TLS/SSL configuration
  ssl-ca = "/run/secrets/ca_certificate.pem"
```

Then mount this file in your `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml`:

```yaml
ia-time-series-analytics-microservice:
  volumes:
    # ... existing volumes ...
    - <absolute path to kapacitor.conf file>:/app/config/kapacitor.conf
```

### 3.3 Update Sample app configuration

Edit your sample app config file:
`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/<sample_app>/time-series-analytics-config/config.json`

```json
{
  "alerts": {
    "mqtt": {
      "mqtt_broker_host": "YOUR_MQTT_BROKER_IP",
      "mqtt_broker_port": "MQTT_PORT",
      "name": "my_mqtt_broker"
    }
  }
}
```

**Replace:**
- `YOUR_MQTT_BROKER_IP` with your broker's IP or hostname
- `MQTT_PORT` with your broker's TLS port

## Step 4: Configure Your External MQTT Broker

### For Mosquitto Broker

If you're using Mosquitto as your external broker, configure it to use the certificates:

```
# /etc/mosquitto/mosquitto.conf

# Secure listener
listener <MQTT_PORT>
protocol mqtt

# Certificate files (copy these to your broker)
cafile /etc/mosquitto/certs/ca_cert.pem
certfile /etc/mosquitto/certs/server_certificate.pem
keyfile /etc/mosquitto/certs/server.key
allow_anonymous true
```

Copy certificates to your MQTT broker:
```bash
# On your MQTT broker server
sudo mkdir -p /etc/mosquitto/certs
sudo cp ca_cert.pem server_certificate.pem server.key /etc/mosquitto/certs/
sudo chown mosquitto:mosquitto /etc/mosquitto/certs/*
sudo chmod 644 /etc/mosquitto/certs/*.pem
sudo chmod 600 /etc/mosquitto/certs/*.key
```

## Step 5: Deploy and Verify

Deploy the sample application following the steps as mentioned [here](../get-started.md#deploy-with-docker-compose).
