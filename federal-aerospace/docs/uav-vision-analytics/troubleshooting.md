# Troubleshooting

## QGroundControl — "Network Not Available" warnings

**Symptom:** The following warnings appear in the QGroundControl logs:

```
16.701 Warning: 1 "Network Not Available" - QtLocationPlugin.QGeoTiledMapReplyQGC - (unknown:0)
```

**Cause:** NetworkManager's connectivity check is failing, which causes it to report the network as `limited` or `none` even when the host has a valid local connection.

**Resolution:**

1. Confirm the connectivity state:

    ```bash
    nmcli networking connectivity check   # expected: "limited" or "none"
    ```

2. Disable the NetworkManager connectivity check:

    ```bash
    sudo mkdir -p /etc/NetworkManager/conf.d
    sudo tee /etc/NetworkManager/conf.d/20-connectivity.conf <<'EOF'
    [connectivity]
    enabled=false
    EOF
    sudo systemctl restart NetworkManager
    ```

3. Verify the state is now reported as full:

    ```bash
    nmcli networking connectivity check   # expected: "full"
    ```

---

## PX4 SITL — image pull or runtime issues

**Symptom:** The `px4` service in Docker Compose fails to start or behaves unexpectedly when using the `latest` tag.

**Resolution:** Pin the PX4 SITL image to a known-good digest in `docker-compose-pymavlink.yml`:

```diff
-image: px4io/px4-sitl:latest
+image: px4io/px4-sitl@sha256:01866d912ac22ca6119a996b830cf628a6d47dfb60fdccc41cd9f44b62935a44
```

---

## QGroundControl — outdated version

If QGroundControl itself behaves unexpectedly, ensure you are running the latest stable release.
Installation instructions for Ubuntu: <https://docs.qgroundcontrol.com/master/en/qgc-user-guide/getting_started/download_and_install.html#ubuntu>
