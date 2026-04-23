# Troubleshooting

1. Inference on GPU does not work?

   ```bash
   sudo -E apt install clinfo
   clinfo
   ```

   Verify that the GPU is part of supported platforms:

   ```text
   Number of platforms                             1
   Platform Name                                   Intel(R) OpenCL HD Graphics
   Platform Vendor                                 Intel(R) Corporation
   Platform Version                                OpenCL 3.0
   Platform Profile                                FULL_PROFILE
   ```

2. Robot does not move?

   First start the motion controller, then press play on the pendant.

3. Robot arm does not go accurately pick up the object?

   Check [Camera pose calibration](use_cases/dynamic_use_case/system_config.rst#camera_integration)
