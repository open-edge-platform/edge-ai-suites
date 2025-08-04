These scripts may be used to build the collaborative SLAM Debian packages from source code and install them into your system.

It is recommended these scripts be used with the development container supplied here: `applications.robotics.mobile.amr-common/dev/dev-container/`

Remember to either adjust the hard-coded folder path contained in each script, or set the appropriate environment variable[s] used within, to match your development environment.

- Use `dpkg-build.sh` to build and generate local .deb files. Specify an input parameters: 0 (default) - all, 1 - msgs, 2 - slam/openvslam, 3 - tracker, 4 - server
- Use `dpkg-install.sh` to install local Debian packages from .deb file. Specify an input parameter: 1 (default) - SSE CPU, 2 - LZE GPU, 3 - AVX2 CPU
- Use `incr-build.sh` to compile the C-SLAM incrementally. Specify an input parameter: 1 (default) - SSE CPU, 2 - LZE GPU, 3 - AVX2 CPU
