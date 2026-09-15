import os
import threading
import json
import paho.mqtt.client as mqtt
from gstgva import VideoFrame

MQTT_BROKER      = 'host.docker.internal'
MQTT_PORT        = 1884
UAV_ID           = os.environ.get('UAV_ID', 'uav-1')
MQTT_TOPIC_PREFIX = f'uav/{UAV_ID}/telemetry/#'

lock = threading.Lock()

latest_data = {
    "altitude": 0.0,
    "speed": 0.0,
    "heading": 0.0,
    "latitude": 0.0,
    "longitude": 0.0,
    "gps_altitude": 0.0,
    "gps_fix": 0,
    "satellites": 0
}


class MqttReceiver(threading.Thread):

    def __init__(self):
        super().__init__(daemon=True)
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT broker")
            client.subscribe(f"{MQTT_TOPIC_PREFIX}")
        else:
            print(f"Failed to connect to MQTT broker, return code {rc}")

    def _on_message(self, client, userdata, message):

        try:
            topic     = message.topic
            msg_type  = topic.split('/')[-1]
            data      = json.loads(message.payload.decode())
        except (ValueError, IndexError):
            return

        with lock:
            if msg_type == "position":
                latest_data["altitude"] = data.get("relative_altitude_m", 0.0)
                latest_data["latitude"] = data.get("latitude_deg", 0.0)
                latest_data["longitude"] = data.get("longitude_deg", 0.0)
                latest_data["gps_altitude"] = data.get("absolute_altitude_m", 0.0)
            elif msg_type == "attitude":
                latest_data["heading"] = data.get("yaw_deg", 0.0)
            elif msg_type == "velocity":
                north = data.get("north_m_s", 0.0)
                east = data.get("east_m_s", 0.0)
                down = data.get("down_m_s", 0.0)

                latest_data["speed"] = (
                    north ** 2 + east ** 2 + down ** 2
                ) ** 0.5
            elif msg_type == "gps":
                latest_data["gps_fix"] = data.get("fix_type", "")
                latest_data["satellites"] = data.get("num_satellites", 0)

    def run(self):
        print("Connecting to MQTT broker...")
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_forever()

    def stop(self):
        self.client.disconnect()


class DrawDynamicText:

    def __init__(self, name="SDK Telemetry Overlay"):
        self.frame_number = 0
        self.receiver = MqttReceiver()
        self.receiver.start()
        self.name = name

    def process_frame(self, frame: VideoFrame):

        self.frame_number += 1

        with lock:

            altitude    = latest_data["altitude"]
            speed       = latest_data["speed"]
            heading     = latest_data["heading"]

            latitude    = latest_data["latitude"]
            longitude   = latest_data["longitude"]
            gps_altitude = latest_data["gps_altitude"]
            gps_fix     = latest_data["gps_fix"]
            satellites  = latest_data["satellites"]

            lines = [
                f"Name  : {self.name}",
                f"Frame : {self.frame_number}",
                f"ALT   : {altitude:.1f} m",
                f"SPD   : {speed:.1f} m/s",
                f"HDG   : {heading:.1f}",
                f"LAT   : {latitude:.7f}",
                f"LON   : {longitude:.7f}",
                f"SATS  : {satellites}"
            ]

            y = 20

        width  = frame.video_info().width
        height = frame.video_info().height

        for line in lines:
            roi = frame.add_region(
                10,
                y,
                1,
                1,
                line
            )
            roi.confidence = 1.0
            y += 22

        return True
