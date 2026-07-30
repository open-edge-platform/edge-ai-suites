#!/bin/bash

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

tc_error() { 
    printf "Error: TC installation not found.\n" >&2 
    exit 1
}

cleanup() {
    if [ "$(docker ps -aq -f name=^tc-nginx$)" ]; then
        docker rm -f tc-nginx >/dev/null 2>&1
    fi
}

trap 'cleanup' EXIT

REQUIRED_PATHS=(
    "/usr/bin/containerd-shim-kata-v2"
    "/opt/kata"
    "/etc/kata-containers/configuration.toml"
)

for path in "${REQUIRED_PATHS[@]}"; do
    if [[ ! -e "$path" ]]; then
        echo "Missing requirement: $path" >&2
        tc_error
    fi
done

# Test if we can run a container with the TC
cleanup
docker run -d \
    --name tc-nginx \
    --runtime io.containerd.kata.v2 \
    nginx:1.27.0 &>/dev/null || tc_error

#check if ntc-nginx is running with containerd-shim-kata-v2
sleep 3
sandbox_id=$(docker inspect tc-nginx --format='{{.Id}}' 2>/dev/null)
ps aux | grep "containerd-shim-kata-v2" | grep -v grep | grep -q "$sandbox_id" || tc_error
cleanup

ENV_FILE="../.env"

#Configure TC network settings and create resolv.conf for DNS relay
if [ -z "$TC_SUBNET" ]; then
    TC_SUBNET=172.20.0.0/16
    TC_DNS_IP=172.20.0.200
else
    #check if TC_SUBNET is in valid format
    if ! [[ "$TC_SUBNET" =~ ^172\.([0-9]+)\.0\.0/16$ ]] || [ "${BASH_REMATCH[1]}" -lt 18 ] || [ "${BASH_REMATCH[1]}" -gt 31 ]; then
        echo "Error: TC_SUBNET must be exactly 172.X.0.0/16 where X is 18-31 (current: ${TC_SUBNET})"
        exit 1
    fi
    #update .env file with TC_SUBNET
    if grep -q "^TC_SUBNET=" "$ENV_FILE"; then
        sed -i "s|^TC_SUBNET=.*|TC_SUBNET=${TC_SUBNET}|" "$ENV_FILE"
    else
        echo "TC_SUBNET=${TC_SUBNET}" >> "$ENV_FILE"
    fi
    #calculate TC_DNS_IP based on TC_SUBNET and update .env file
    TC_DNS_IP="$(echo "$TC_SUBNET" | sed -E 's/\.[0-9]+\/[0-9]+$//').200"
    if grep -q "^TC_DNS_IP=" "$ENV_FILE"; then
        sed -i "s|^TC_DNS_IP=.*|TC_DNS_IP=${TC_DNS_IP}|" "$ENV_FILE"
    else
        echo "TC_DNS_IP=${TC_DNS_IP}" >> "$ENV_FILE"
    fi
fi

echo "nameserver ${TC_DNS_IP}" > "../tc-resolv.conf"
echo "Configuring TC network settings - Subnet: ${TC_SUBNET}, DNS Relay IP: ${TC_DNS_IP}"

# VFIO GPU Detection for TC + GPU mode
if [ "${TC_SI_TARGET_DEVICE}" = "GPU" ]; then
    # Detect Intel iGPU PCI address using lspci -Dnn (includes domain prefix)
    GPU_PCI_FULL=$(lspci -Dnn | grep -E '(VGA compatible controller|Display controller).*Intel' | head -1 | awk '{print $1}')
    if [ -z "$GPU_PCI_FULL" ]; then
        echo "Error: No Intel iGPU found." >&2
        exit 1
    fi

    # Read IOMMU group from sysfs
    IOMMU_LINK="/sys/bus/pci/devices/${GPU_PCI_FULL}/iommu_group"
    if [ ! -L "$IOMMU_LINK" ]; then
        echo "Error: No IOMMU group found for ${GPU_PCI_FULL}. Ensure IOMMU is enabled." >&2
        exit 1
    fi
    export TC_GPU_VFIO_GROUP=$(basename "$(readlink -f "$IOMMU_LINK")")

    # Verify GPU is bound to vfio-pci and /dev/vfio/<n> exists
    if [ ! -e "/dev/vfio/${TC_GPU_VFIO_GROUP}" ]; then
        echo "Error: /dev/vfio/${TC_GPU_VFIO_GROUP} not found. Ensure GPU is bound to vfio-pci." >&2
        exit 1
    fi
    # Write TC_GPU_VFIO_GROUP to root .env so docker compose can resolve ${TC_GPU_VFIO_GROUP}
    if grep -q "^TC_GPU_VFIO_GROUP=" "$ENV_FILE"; then
        sed -i "s|^TC_GPU_VFIO_GROUP=.*|TC_GPU_VFIO_GROUP=${TC_GPU_VFIO_GROUP}|" "$ENV_FILE"
    else
        echo "TC_GPU_VFIO_GROUP=${TC_GPU_VFIO_GROUP}" >> "$ENV_FILE"
    fi
fi

echo "Trusted Compute security enabled"
