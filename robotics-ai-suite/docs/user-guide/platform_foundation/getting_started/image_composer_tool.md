# Image Composer Tool Setup

An alternative method for setup is to create a pre-configured OS image with ROS 2 and the appropriate repositories using the Image Composer Tool. This approach is similar to the Express Setup convenience script above, but instead of configuring an existing system, it creates a complete bootable OS image that can be deployed to multiple systems or used for fresh installations.

Image Composer Tool supports creating both ISO images (for installation via USB) and raw disk images (for direct deployment to storage devices or VMs). ISO images are suitable for interactive installations, while raw images can be directly written to storage media or VMs for immediate use. If you prefer to start with a base Ubuntu installation, without needing to reimage a system, use the [Express Setup](express.md) or the [Step-by-step Setup](step_by_step.md) guide.

For detailed instructions, see the [Image Composer Tool repository](https://github.com/open-edge-platform/image-composer-tool). An abbreviated ISO image creation follows:

1. Install Go (Go 1.24+ required) + build dependencies:

   ```bash
   sudo apt update && sudo apt install golang-1.24 git systemd-ukify mmdebstrap
   ```

2. Update go path since 1.24 isn't default:

   ```bash
   export PATH=$PATH:/usr/lib/go-1.24/bin
   source ~/.bashrc
   ```

3. Clone Image Composer Tool repository:

   ```bash
   git clone https://github.com/open-edge-platform/image-composer-tool.git
   cd image-composer-tool
   ```

4. Build the tool (output: ``./image-composer-tool``):

   ```bash
   go build -buildmode=pie -ldflags "-s -w" ./cmd/image-composer-tool
   ```

5. Build the live-installer (required for ISO images):

   ```bash
   go build -buildmode=pie -o ./build/live-installer -ldflags "-s -w" ./cmd/live-installer
   ```

6. Build ISO image:

   ```bash
   sudo -E ./image-composer-tool build image-templates/ubuntu24-x86_64-robotics-jazzy-iso.yml
   ```

7. Once image is successfully built, modify the below command to point to the built image location (shown after build). Change ``/dev/sdX`` to proper USB drive location (i.e. ``/dev/sdb``). Flash ISO Image to USB drive:

   ```bash
   sudo dd if=builds/robotics-jazzy-ubuntu24-24.04.iso of=/dev/sdX bs=4M status=progress conv=fsync
   ```

8. Boot from the USB drive and install the image to your system.

9. **Setup complete!** Next Steps: Explore the [Tutorials](../../components/optimized_solutions/index.md) for ready-to-use applications and examples.
