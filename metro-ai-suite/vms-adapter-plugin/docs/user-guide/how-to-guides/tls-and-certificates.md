# TLS and Certificate Configuration

This guide explains how to configure certificate verification for these external connections used by the VMS Adapter Plugin (VAP):

- Nx Witness HTTPS
- DLStreamer Vision HTTPS
- MQTT subscribing for dls_vision metadata
- MQTT subscribing for the Live Video Captioning (LVC) broker

This page covers client-side TLS only. Server-side broker hardening, topic ACLs, and certificate issuance are managed outside VAP.

## What VAP Verifies

VAP acts as a client in three separate places:

- HTTPS client to Nx Witness
- HTTPS client to the DLS Vision analytics app
- MQTT client to one or two brokers, depending on which analytics apps are enabled

Certificate verification is controlled independently for each connection family.

## Certificate File Paths

The backend container mounts `./config` from the repository to `/app/config` inside the container through `docker-compose.yml`.

That means certificate files placed on the host under `./config/certs/` are available inside the container as `/app/config/certs/...`.

Recommended host directory layout:

```text
config/
  certs/
    nx-ca.crt
    dls-vision-ca.crt
    mqtt-ca.crt
    mqtt-client.crt
    mqtt-client.key
    lvc-mqtt-ca.crt
    lvc-mqtt-client.crt
    lvc-mqtt-client.key
```

Use the container paths in `.env`, not the host paths.

## Nx Witness HTTPS

Nx certificate verification is controlled by these variables:

```dotenv
NX_TLS_VERIFY=false
NX_CA_BUNDLE=
```

Behavior:

- `NX_TLS_VERIFY=false`: VAP does not verify the Nx server certificate.
- `NX_TLS_VERIFY=true` with `NX_CA_BUNDLE` empty: VAP uses the container's default system CA store.
- `NX_TLS_VERIFY=true` with `NX_CA_BUNDLE=/app/config/certs/nx-ca.crt`: VAP verifies Nx using the provided CA bundle.

Typical self-signed or private-CA setup:

1. Copy the Nx server certificate or issuing CA certificate to `./config/certs/nx-ca.crt`.
2. Set:

```dotenv
NX_TLS_VERIFY=true
NX_CA_BUNDLE=/app/config/certs/nx-ca.crt
```
To generate and add your own self signed certificate for Nx, see [How to generate and add a self signed trusted certificate](https://support.networkoptix.com/hc/en-us/articles/16635062678039-How-to-generate-and-add-a-self-signed-trusted-certificate)

For more information about Nx Witness security, see [How secure is Nx Witness](https://support.networkoptix.com/hc/en-us/articles/115011970028-How-secure-is-Nx-Witness).

## DLS Vision HTTPS

DLS Vision certificate verification is controlled by these variables:

```dotenv
DLS_VISION_TLS_VERIFY=false
DLS_VISION_CA_BUNDLE=
```

Behavior:

- `DLS_VISION_TLS_VERIFY=false`: VAP does not verify the DLS Vision server certificate.
- `DLS_VISION_TLS_VERIFY=true` with `DLS_VISION_CA_BUNDLE` empty: VAP uses the container's default system CA store.
- `DLS_VISION_TLS_VERIFY=true` with `DLS_VISION_CA_BUNDLE=/app/config/certs/dls-vision-ca.crt`: VAP verifies DLS Vision using the provided CA bundle.

Typical self-signed or private-CA setup:

1. Copy the DLS Vision server certificate or issuing CA certificate to `./config/certs/dls-vision-ca.crt`.
2. Set:

```dotenv
DLS_VISION_TLS_VERIFY=true
DLS_VISION_CA_BUNDLE=/app/config/certs/dls-vision-ca.crt
```

## MQTT Subscribing for dls_vision

These variables control the MQTT client used by the object detection subscriber:

```dotenv
MQTT_HOST=host.docker.internal
MQTT_PORT=1883
MQTT_TLS_ENABLED=false
MQTT_CA_BUNDLE=
MQTT_CLIENT_CERT=
MQTT_CLIENT_KEY=
```

Behavior:

- `MQTT_TLS_ENABLED=false`: plain MQTT is used. All MQTT TLS fields are ignored.
- `MQTT_TLS_ENABLED=true` with `MQTT_CA_BUNDLE` empty: VAP verifies the broker certificate using the default system CA store.
- `MQTT_TLS_ENABLED=true` with `MQTT_CA_BUNDLE` set: VAP verifies the broker certificate using that CA bundle.
- `MQTT_CLIENT_CERT` and `MQTT_CLIENT_KEY` set together: VAP also presents a client certificate to the broker for mutual TLS.

Typical server-auth TLS setup:

```dotenv
MQTT_HOST=host.docker.internal
MQTT_PORT=8883
MQTT_TLS_ENABLED=true
MQTT_CA_BUNDLE=/app/config/certs/mqtt-ca.crt
MQTT_CLIENT_CERT=
MQTT_CLIENT_KEY=
```

Typical mutual TLS setup:

```dotenv
MQTT_HOST=host.docker.internal
MQTT_PORT=8883
MQTT_TLS_ENABLED=true
MQTT_CA_BUNDLE=/app/config/certs/mqtt-ca.crt
MQTT_CLIENT_CERT=/app/config/certs/mqtt-client.crt
MQTT_CLIENT_KEY=/app/config/certs/mqtt-client.key
```

Notes:

- VAP does not change the MQTT port automatically when TLS is enabled. If your broker exposes TLS on `8883`, set `MQTT_PORT=8883` explicitly.
- If only one of `MQTT_CLIENT_CERT` or `MQTT_CLIENT_KEY` is set, subscriber startup fails when Python tries to load the certificate chain.
- This TLS configuration secures the connection to the broker, but it does not replace broker ACLs or topic authorization.

## MQTT Subscribing for LVC

These variables control the top-level MQTT client used for the LVC broker connection:

```dotenv
MQTT_BROKER_HOST=host.docker.internal
MQTT_BROKER_PORT=1883
MQTT_BROKER_TLS_ENABLED=false
MQTT_BROKER_CA_BUNDLE=
MQTT_BROKER_CLIENT_CERT=
MQTT_BROKER_CLIENT_KEY=
```

Behavior is the same as for the dls_vision MQTT subscriber:

- `MQTT_BROKER_TLS_ENABLED=false`: plain MQTT is used.
- `MQTT_BROKER_TLS_ENABLED=true` with `MQTT_BROKER_CA_BUNDLE` empty: VAP uses the default system CA store.
- `MQTT_BROKER_TLS_ENABLED=true` with `MQTT_BROKER_CA_BUNDLE` set: VAP verifies the broker certificate using that CA bundle.
- `MQTT_BROKER_CLIENT_CERT` and `MQTT_BROKER_CLIENT_KEY` set together: VAP uses mutual TLS.

Example:

```dotenv
MQTT_BROKER_HOST=host.docker.internal
MQTT_BROKER_PORT=8883
MQTT_BROKER_TLS_ENABLED=true
MQTT_BROKER_CA_BUNDLE=/app/config/certs/lvc-mqtt-ca.crt
MQTT_BROKER_CLIENT_CERT=/app/config/certs/lvc-mqtt-client.crt
MQTT_BROKER_CLIENT_KEY=/app/config/certs/lvc-mqtt-client.key
```

## Example `.env` Snippet

```dotenv
# Nx Witness
NX_TLS_VERIFY=true
NX_CA_BUNDLE=/app/config/certs/nx-ca.crt

# DLS Vision HTTPS
DLS_VISION_TLS_VERIFY=true
DLS_VISION_CA_BUNDLE=/app/config/certs/dls-vision-ca.crt

# dls_vision MQTT subscriber
MQTT_HOST=host.docker.internal
MQTT_PORT=8883
MQTT_TLS_ENABLED=true
MQTT_CA_BUNDLE=/app/config/certs/mqtt-ca.crt
MQTT_CLIENT_CERT=/app/config/certs/mqtt-client.crt
MQTT_CLIENT_KEY=/app/config/certs/mqtt-client.key

# LVC MQTT subscriber
MQTT_BROKER_HOST=host.docker.internal
MQTT_BROKER_PORT=8883
MQTT_BROKER_TLS_ENABLED=true
MQTT_BROKER_CA_BUNDLE=/app/config/certs/lvc-mqtt-ca.crt
MQTT_BROKER_CLIENT_CERT=/app/config/certs/lvc-mqtt-client.crt
MQTT_BROKER_CLIENT_KEY=/app/config/certs/lvc-mqtt-client.key
```

## Restart After Changes

After updating certificates or `.env`, recreate the backend container:

```bash
docker compose up -d --force-recreate backend
```

## Troubleshooting

- Certificate path errors: confirm the file exists inside the container at the exact `/app/config/certs/...` path.
- TLS enabled but connection still fails: verify the broker or HTTPS service is actually listening on the configured TLS port.
- Private CA deployments: if verification is enabled and the CA bundle is empty, the system CA store may not trust your internal CA.
- Mutual TLS failures: ensure the client certificate and key match and are both readable inside the container.

## Security Disclaimer

This guide documents VAP client-side TLS settings only. For MQTT deployments, you should still configure the broker itself with appropriate listener settings, topic ACLs, and certificate policy.