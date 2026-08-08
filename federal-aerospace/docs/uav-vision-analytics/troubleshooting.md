# Troubleshooting

## QGC connectivity issue
If you observe issue like the following in the logs of the QgroundControl application, it is likely that the system is unable to reach the internet. This can happen if the network connectivity check fails.
    16.701 Warning: 1 "Network Not Available" - QtLocationPlugin.QGeoTiledMapReplyQGC - (unknown:0)
    16.701 Warning: 1 "Network Not Available" - QtLocationPlugin.QGeoTiledMapReplyQGC - (unknown:0)

Following are the troubleshooting steps
nmcli networking connectivity check   # likely shows "limited" or "none"
sudo mkdir -p /etc/NetworkManager/conf.d
sudo tee /etc/NetworkManager/conf.d/20-connectivity.conf <<'EOF'
[connectivity]
enabled=false
EOF
sudo systemctl restart NetworkManager
nmcli networking connectivity check   # should now show "full"
