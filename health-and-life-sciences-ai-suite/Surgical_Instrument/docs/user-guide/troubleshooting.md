# Troubleshooting

1. `docker compose up` fails with `permission denied` on `/dev/dri/renderD128`
   - The `render` group GID inside the container does not match the host.
     Confirm `getent group render` on the host and re-run `make up` (the Makefile auto-detects).
2. `surgical-backend` never becomes healthy; logs show `preparing_dataset → error`
   - The ColonDB archive isn't at `datasets/ColonDB/raw/`. See step 2 of the
     [Get Started](./quickstart.md#2-one-time-drop-the-ColonDB-dataset).
3. Browser at `http://localhost:8080` returns "connection refused"
   - The UI is still waiting for the backend HEALTHCHECK. `docker ps` will show `surgical-ui`
     as `Created` (not `Up`). Follow `make logs surgical-backend` until you see `state=ready`.
4. Training runs on CPU instead of iGPU (very slow)
   - The container did not see `/dev/dri`. Check `docker exec surgical-backend ls /dev/dri`
     and `python -c "import torch; print(torch.xpu.is_available())"`.
5. `torch.xpu` prints `False` inside the container
   - Level-Zero library missing. The backend image ships `libze1`; if your host has a
     mismatched driver, install `intel-i915-dkms` (or the equivalent for your kernel)
     and reboot.


