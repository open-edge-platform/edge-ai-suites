#!/bin/bash
# Smart Building Digital Twin Blueprint
# Generate self-signed TLS certificates and secrets for Scenescape

set -e

CERT_DIR="./certs"
mkdir -p "$CERT_DIR"
# Migrate legacy layout where django was a plain file
if [ -f "$CERT_DIR/django" ]; then
  rm -f "$CERT_DIR/django"
fi
mkdir -p "$CERT_DIR/django"

echo "Generating TLS certificates and secrets..."

generate_server_cert() {
  local host_short="$1"
  local key_path="$2"
  local csr_path="$3"
  local crt_path="$4"
  local san_config
  san_config=$(mktemp)

  cat > "$san_config" <<EOF
[req]
distinguished_name = req_distinguished_name
prompt = no
req_extensions = req_ext

[req_distinguished_name]
commonName = ${host_short}.scenescape.intel.com

[req_ext]
subjectAltName = @alt_names

[x509_ext]
subjectKeyIdentifier = hash
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${host_short}.scenescape.intel.com
DNS.2 = ${host_short}
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

  openssl genrsa -out "$key_path" 2048 2>/dev/null
  openssl req -new -key "$key_path" -out "$csr_path" -config "$san_config" 2>/dev/null
  openssl x509 -req -in "$csr_path" \
    -CA "$CERT_DIR/scenescape-ca.pem" -CAkey "$CERT_DIR/scenescape-ca.key" \
    -CAcreateserial -out "$crt_path" -days 3650 \
    -extensions x509_ext -extfile "$san_config" 2>/dev/null

  rm -f "$san_config"
}

# Generate CA (Certificate Authority)
openssl genrsa -out "$CERT_DIR/scenescape-ca.key" 2048 2>/dev/null
openssl req -new -x509 -days 3650 -key "$CERT_DIR/scenescape-ca.key" \
  -out "$CERT_DIR/scenescape-ca.pem" \
  -subj "/CN=scenescape-local-ca" 2>/dev/null

# Generate MQTT broker certificate
generate_server_cert \
  broker \
  "$CERT_DIR/scenescape-broker.key" \
  "$CERT_DIR/scenescape-broker.csr" \
  "$CERT_DIR/scenescape-broker.crt"

# Generate web UI certificate
generate_server_cert \
  web \
  "$CERT_DIR/scenescape-web.key" \
  "$CERT_DIR/scenescape-web.csr" \
  "$CERT_DIR/scenescape-web.crt"

# Generate autocalibration certificate
generate_server_cert \
  autocalibration \
  "$CERT_DIR/scenescape-autocalibration.key" \
  "$CERT_DIR/scenescape-autocalibration.csr" \
  "$CERT_DIR/scenescape-autocalibration.crt"

# Generate Django secrets.py in the expected layout
SECRET_KEY=$(python3 -c 'import secrets; print("".join([secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)") for _ in range(50)]))')
DB_PASS=${DATABASE_PASSWORD:-$(openssl rand -base64 12)}
cat > "$CERT_DIR/django/secrets.py" <<EOF
SECRET_KEY='${SECRET_KEY}'
DATABASE_PASSWORD='${DB_PASS}'
EOF
chmod 0644 "$CERT_DIR/django/secrets.py"

# Generate authentication JSON files expected by Scenescape
CONTROLLER_PASS=$(openssl rand -base64 12)
BROWSER_PASS=$(openssl rand -base64 12)
CALIBRATION_PASS=$(openssl rand -base64 12)
cat > "$CERT_DIR/controller.auth" <<EOF
{"user": "scenectrl", "password": "${CONTROLLER_PASS}"}
EOF
cat > "$CERT_DIR/browser.auth" <<EOF
{"user": "webuser", "password": "${BROWSER_PASS}"}
EOF
cat > "$CERT_DIR/calibration.auth" <<EOF
{"user": "calibration", "password": "${CALIBRATION_PASS}"}
EOF
chmod 0644 "$CERT_DIR/controller.auth" "$CERT_DIR/browser.auth" "$CERT_DIR/calibration.auth"

# Clean up CSR files
rm -f "$CERT_DIR"/*.csr "$CERT_DIR"/*.srl

echo "  ✓ Certificates and secrets generated in $CERT_DIR/"
