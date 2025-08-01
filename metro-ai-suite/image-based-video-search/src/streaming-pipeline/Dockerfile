FROM ghcr.io/open-edge-platform/edge-ai-libraries/intel/edge-ai-dlstreamer:20250729_EAL1.2_DLS_RC2-ubuntu22

USER root

RUN apt-get update && apt-get install --yes gstreamer1.0-plugins-ugly wget

USER dlstreamer

ENV GST_PLUGIN_PATH=$GST_PLUGIN_PATH/usr/lib/x86_64-linux-gnu/gstreamer-1.0/

RUN pip install opencv-python-headless

# Conditional installation of source code
USER root

ARG INSTALL_SOURCES=no

RUN if [ "$INSTALL_SOURCES" = "yes" ]; then \
        apt-get update && \
        sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources && \
        apt-get update && \
        root_dir=$PWD && \
        mkdir -p ./apt-sources/IBVS && cd ./apt-sources/IBVS && \
        SOURCE_DIR='./apt-sources/copyleft' && \
        mkdir -p $SOURCE_DIR && cd $SOURCE_DIR && \
        echo -n $null > copyleft_package_list.txt && \
        for package in $(dpkg -l | awk '/^ii/ {print $2}'); do \
            grep -l 'Copyleft\|GPL\|AGPL\|LGPL\|EPL\|MPL\|CDDL\|GPL-2\|GPL-3.0\|AGPL-3.0\|LGPL-3.0\|EPL-2.0\|MPL-1.1\|MPL-2.0' /usr/share/doc/${package}/copyright; \
            exit_status=$?; \
            if [ $exit_status -eq 0 ]; then \
                echo $package >> copyleft_package_list.txt; \
                apt-get source -q --download-only $package; \
            fi; \
        done; \
        echo "Download source for $(ls | wc -l) third-party packages: $(du -sh)"; \
        rm -rf /var/lib/apt/lists/*; \
    fi

USER dlstreamer