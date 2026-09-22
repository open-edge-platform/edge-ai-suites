# Troubleshooting

| Symptom | Probable Cause | Fix |
| :--- | :--- | :--- |
| **No Axle Counts** | Wrong Adapter | Ensure `config.json` points to `sscape_adapter_side.py`. |
| **"Lift Axles" counted as Ground** | Tolerance too high | Adjust `tolerance` parameter in `classify_axles_ground_contact` function. |
| **Grafana Empty** | Node-RED Disconnect | Check `docker logs node-red`. Ensure connection to `broker.scenescape.intel.com` or local broker. |
| **No Video** | GPU Mapping | Verify `/dev/dri` is mapped in `docker-compose.yml` and user has permissions. |

## Support Contact

If you run into an unexpected problem or need help with the application, you can
browse existing issues or
[create a new one](https://github.com/open-edge-platform/edge-ai-suites/issues)
in the GitHub issue tracker.
