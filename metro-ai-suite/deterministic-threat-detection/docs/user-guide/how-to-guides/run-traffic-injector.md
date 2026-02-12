# Run the Traffic Injector

This guide explains how to use iPerf3 to inject best-effort background traffic into the
network. This allows you to observe the impact of network congestion on your time-sensitive
traffic and validate the effectiveness of TSN traffic shaping.

## Overview

iPerf3 is a modern, widely used network testing tool that can create data streams to
measure network performance. In this use case, we use iPerf3 to generate background traffic
that competes for network resources with the critical video and sensor data streams.

The setup involves two machines:

-   An **iPerf3 server** that listens for incoming traffic.
-   An **iPerf3 client** that sends data to the server.

## Prerequisites

Ensure iPerf3 is installed on both the client and server machines.

```bash
sudo apt-get update
sudo apt-get install -y iperf3
```

## Running the Traffic Injector

Follow these steps to start the traffic injection.

### 1. Start the iPerf3 Server

On the machine that will receive the traffic (e.g., Machine 4, the MQTT Aggregator), run the
following command to start the iPerf3 server in the background.

```bash
iperf3 -s &
```

The server will now be listening for connections on the default port (5201).

### 2. Start the iPerf3 Client

On the machine designated as the traffic injector (Machine 5), run the following command to
start sending UDP traffic to the iPerf3 server.

```bash
iperf3 -c <IPERF_SERVER_IP> -u -b 200M -t 3600
```

Replace `<IPERF_SERVER_IP>` with the IP address of the machine running the iPerf3 server.
