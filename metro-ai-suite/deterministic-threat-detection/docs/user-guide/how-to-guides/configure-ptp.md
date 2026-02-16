# Synchronize PTP Time (IEEE 802.1AS)

## What is PTP?

Precision Time Protocol (PTP) provides sub-microsecond time synchronization across Ethernet
devices, enabling accurate latency measurements.

## Install PTP Tools

```bash
sudo apt-get update
sudo apt-get install -y linuxptp git
git clone https://git.code.sf.net/p/linuxptp/code linuxptp
cd linuxptp
```

## PTP Commands

The TSN switch is configured to act as the PTP Grandmaster clock. On each Arrow Lake machine,
execute the following command to synchronize the system clock using PTP.

> **Note:** Make sure to replace `enp1s0` with the actual network interface name associated
> with the `i226` network card.

1. **Start the PTP daemon (`ptp4l`)**

   Start the `ptp4l` daemon on each machine, specifying the network interface (`enp1s0`)
   related to the i226 network on that machine and the gPTP configuration file.

   ```bash
   sudo ptp4l -i enp1s0 -f configs/gPTP.cfg --step_threshold=1 -m -s
   ```

2. **Synchronize the System Clock (`phc2sys`)**

   Synchronize the system clock with the PTP hardware clock (PHC).

   ```bash
   sudo phc2sys -s enp1s0 -c CLOCK_REALTIME --step_threshold=1 --transportSpecific=1 -w -m
   ```

3. **Verify Synchronization**

   Check the `phc2sys` output to ensure the offset is within acceptable limits (e.g., less
   than 50ns). The output should look similar to this:

   ```text
   phc2sys[1234.567]: CLOCK_REALTIME phc offset 12345 s0 freq +0 delay 1234
   ```
