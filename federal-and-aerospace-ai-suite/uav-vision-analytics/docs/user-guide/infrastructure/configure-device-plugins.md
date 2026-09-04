<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# GPU and NPU Device Plugins Usage Guide

## Overview

Intel GPU and NPU device plugins expose hardware accelerators to Kubernetes pods without requiring privileged containers. The plugins register devices with the kubelet via the Kubernetes Device Plugin framework, allowing pods to request accelerators through standard resource limits — `gpu.intel.com/xe` for GPU and `npu.intel.com/accel` for NPU.

The Edge Node Infrastructure software pre-installs these plugins during first boot. This guide covers verification, pod scheduling, and common usage patterns.

| Resource Name | Plugin | Hardware | Use Case |
|---------------|--------|----------|----------|
| `gpu.intel.com/xe` | Intel GPU device plugin | Intel Xe-based integrated/discrete GPU (including SR-IOV VFs) | Media processing, inference, rendering |
| `npu.intel.com/accel` | Intel NPU device plugin | Intel NPU 2000/3000/4000 series | Low-power AI inference |

---

## Prerequisites

- Edge Node Infrastructure software image deployed with Kubernetes (K3s) host type
- Intel GPU and/or NPU hardware present
- K3s running with device plugins installed

---

## Step 1: Verify Plugin Installation

After first boot, confirm that the device plugin pods are running:

```bash
# Check device plugin pods
kubectl get pods -n intel-device-plugins
```

Check all pods across namespaces:

```bash
sudo kubectl get pods -A
```

Expected healthy output includes the running Intel and Node Feature Discovery components:

```text
intel-device-plugins     intel-gpu-plugin-xxxxx                  1/1   Running
intel-device-plugins     intel-npu-plugin-xxxxx                  1/1   Running
node-feature-discovery   nfd-master-xxxxx                        1/1   Running
node-feature-discovery   nfd-worker-xxxxx                        1/1   Running
```

---

## Step 2: Verify Allocatable Resources

Confirm that the node advertises GPU and NPU resources:

```bash
kubectl describe node | grep -A 20 "Allocatable:"
```

Expected output (example with SR-IOV VFs enabled):

```text
Allocatable:
  cpu:                       xx
  ephemeral-storage:         xxx
  gpu.intel.com/monitoring:  x
  gpu.intel.com/xe:          x
  memory:                    xxx
  npu.intel.com/accel:       x
  pods:                      xxx
```

The `gpu.intel.com/xe` count reflects the number of SR-IOV Virtual Functions available for allocation.

You can also verify the node labels applied by NFD:

```bash
kubectl get nodes --show-labels | tr ',' '\n' | grep intel
```

---

## Step 3: Run a Pod with GPU Access

Create a pod that requests one Intel GPU device:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test
  namespace: default
spec:
  restartPolicy: Never
  containers:
    - name: gpu-check
      image: ubuntu:24.04
      command: ["sh", "-c", "ls -la /dev/dri/ && echo 'GPU accessible'"]
      resources:
        limits:
          gpu.intel.com/xe: "1"
```

Apply and check output:

```bash
kubectl apply -f gpu-test.yaml
kubectl wait pod/gpu-test --for=jsonpath='{.status.phase}'=Succeeded --timeout=60s
kubectl logs gpu-test
```

Expected output:

```text
crw-rw---- 1 root render 226, 129 Jun 17 10:00 renderD129
GPU accessible
```

---

## Step 4: Run a Pod with NPU Access

Create a pod that requests the Intel NPU device:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: npu-test
  namespace: default
spec:
  restartPolicy: Never
  containers:
    - name: npu-check
      image: ubuntu:24.04
      command: ["sh", "-c", "ls -la /dev/accel/ && echo 'NPU accessible'"]
      resources:
        limits:
          npu.intel.com/accel: "1"
```

Apply and check output:

```bash
kubectl apply -f npu-test.yaml
kubectl wait pod/npu-test --for=jsonpath='{.status.phase}'=Succeeded --timeout=60s
kubectl logs npu-test
```

Expected output:

```text
crw-rw---- 1 root render 261, 0 Jun 17 10:00 accel0
NPU accessible
```

---

## Step 5: Run a Pod with Both GPU and NPU

Request both accelerators in a single pod for combined inference workloads:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-npu-test
  namespace: default
spec:
  restartPolicy: Never
  containers:
    - name: accel-check
      image: ubuntu:24.04
      command: ["sh", "-c", "ls /dev/dri/ && ls /dev/accel/ && echo 'Both accelerators accessible'"]
      resources:
        limits:
          gpu.intel.com/xe: "1"
          npu.intel.com/accel: "1"
```

---

## Using GPU/NPU in Deployments

For production workloads, use a Deployment to manage GPU or NPU pods:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inference-app
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: inference
  template:
    metadata:
      labels:
        app: inference
    spec:
      containers:
        - name: inference
          image: ubuntu:24.04
          command: ["sh", "-c", "echo 'GPU device available:' && ls /dev/dri/ && sleep infinity"]
          resources:
            limits:
              gpu.intel.com/xe: "1"
```

The scheduler only places pods on nodes that have available GPU or NPU resources. If the node
has 7 SR-IOV VFs, up to 7 pods can each receive one GPU device.

---

## Troubleshooting

### No GPU/NPU Resources on the Node

1. Check that the device plugin pods are running:

   ```bash
   kubectl get pods -n intel-device-plugins
   kubectl logs -n intel-device-plugins -l app=intel-gpu-plugin
   ```

2. Verify the hardware is detected by the host:

   ```bash
   ls /dev/dri/          # GPU devices
   ls /dev/accel/        # NPU devices
   ```

3. Verify NFD labels are applied:

   ```bash
   kubectl get nodes --show-labels | tr ',' '\n' | grep 'gpu.intel.com'
   kubectl get nodes --show-labels | tr ',' '\n' | grep 'npu.intel.com'
   ```

### Pod Stuck in Pending State

If a pod requesting GPU/NPU is stuck in `Pending`:

```bash
kubectl describe pod <pod-name>
```

Common causes:

- **Insufficient resources**: All GPU/NPU devices are already allocated to other pods
- **No matching node**: The node does not have the requested hardware
- **Plugin not running**: The device plugin pod crashed or was not installed

### GPU Plugin Shows 0 Devices

If SR-IOV VFs are expected but not detected:

```bash
cat /sys/bus/pci/devices/0000:00:02.0/sriov_numvfs
ls /dev/dri/renderD*
```

If VFs are not created, the SR-IOV service may not have run. Check:

```bash
sudo systemctl status intel-sriov-vf.service
sudo journalctl -u intel-sriov-vf.service --no-pager
```

### NPU Plugin Shows 0 Devices

Verify the NPU driver is loaded:

```bash
ls /sys/bus/pci/drivers/intel_vpu/
lsmod | grep intel_vpu
```

If not loaded:

```bash
sudo modprobe intel_vpu
```

For kernel 6.17+, verify firmware:

```bash
ls /lib/firmware/intel/vpu/
dmesg | grep -i vpu
```

---

## References

- [Intel Device Plugins for Kubernetes](https://github.com/intel/intel-device-plugins-for-kubernetes)
- [Intel GPU Plugin Documentation](https://github.com/intel/intel-device-plugins-for-kubernetes/tree/main/cmd/gpu_plugin)
- [Intel NPU Plugin Documentation](https://github.com/intel/intel-device-plugins-for-kubernetes/tree/main/cmd/npu_plugin)
- [Kubernetes Device Plugin Framework](https://kubernetes.io/docs/concepts/extend-kubernetes/compute-storage-net/device-plugins/)
- [Container Device Interface Guide](configure-cdi.md) — for Docker/Podman usage without Kubernetes
