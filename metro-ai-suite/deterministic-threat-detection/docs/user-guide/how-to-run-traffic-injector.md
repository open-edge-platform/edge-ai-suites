# How to Run the Traffic Injector

This guide explains how to use `iperf3` to inject best-effort background traffic into the network. This allows you to observe the impact of network congestion on your time-sensitive traffic and validate the effectiveness of TSN traffic shaping.

## Overview

`iperf3` is a modern, widely used network testing tool that can create data streams to measure network performance. In this use case, we use `iperf3` to generate background traffic that competes for network resources with the critical video and sensor data streams.

The setup involves two machines:
-   An **`iperf3` server** that listens for incoming traffic.
-   An **`iperf3` client** that sends data to the server.

## Prerequisites

Ensure `iperf3` is installed on both the client and server machines.

```bash
sudo apt-get update
sudo apt-get install -y iperf3
```

## Running the Traffic Injector

Follow these steps to start the traffic injection.

### 1. Start the `iperf3` Server

On the machine that will receive the traffic (e.g., Machine 4, the MQTT Aggregator), run the following command to start the `iperf3` server in the background.

```bash
iperf3 -s &
```

The server will now be listening for connections on the default port (5201).

### 2. Start the `iperf3` Client

On the machine designated as the traffic injector (Machine 5), run the following command to start sending UDP traffic to the `iperf3` server.

```bash
iperf3 -c <IPERF_SERVER_IP> -u -b 200M -t 3600
```

Replace `<IPERF_SERVER_IP>` with the IP address of the machine running the `iperf3` server.

