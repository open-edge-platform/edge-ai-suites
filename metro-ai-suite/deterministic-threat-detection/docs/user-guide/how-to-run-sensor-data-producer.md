# How to Run the Sensor Data Producer

This guide explains how to run the `sensor_data_producer.py` script to generate and publish simulated sensor data to an MQTT broker.

## Overview

The `sensor_data_producer.py` script is a Python application that simulates a sensor device. It generates timestamped data packets at a configurable rate and publishes them to a specified MQTT topic. This is useful for testing and demonstrating data pipelines in the TSN sample application.

## Prerequisites

Before running the script, ensure you have Python 3 and the `paho-mqtt` library installed.

```bash
pip install paho-mqtt
```
## MQTT Broker Setup

If you don't have an MQTT broker set up, you can quickly run one using Docker. The following command will start an Eclipse Mosquitto MQTT broker on your machine:

```bash
cd deterministic-threat-detection/sensor_data_producer
docker run -d \
  --name mqtt-broker \
  --network host \
  -v "$(pwd)/configs/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro" \
  eclipse-mosquitto
```

## Running the Script

Navigate to the `deterministic-threat-detection` directory and run the script from there. You need to provide the IP address of the machine where the MQTT aggregator is running or assume `localhost` if --broker is not specified.

```bash
cd deterministic-threat-detection/sensor_data_producer
python3 sensor_data_producer.py --broker <MQTT_BROKER_IP>
```

Replace `<MQTT_BROKER_IP>` with the actual IP address of your MQTT broker.

## Command-Line Arguments

The script supports several command-line arguments to customize its behavior:

| Argument | Description | Default Value |
|---|---|---|
| `--broker` | The IP address or hostname of the MQTT broker. | `localhost` |
| `--port` | The port number for the MQTT broker. | `1883` |
| `--topic` | The MQTT topic to publish the sensor data to. | `sample/sensor/data` |
| `--rate` | The rate in Hertz (Hz) at which to publish data. | `30` |

### Example

To publish data to a broker at `192.168.1.100` on topic `factory/sensors` at a rate of 50 Hz, you would use the following command:

```bash
python3 sensor_data_producer.py --broker 192.168.1.100 --topic factory/sensors --rate 50
```
