import threading
from pymavlink import mavutil
from gstgva import VideoFrame

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


class MavlinkReceiver(threading.Thread):

    def __init__(self):
        super().__init__(daemon=True)
        self.running = True

    def run(self):

        master = mavutil.mavlink_connection(
            "udp:0.0.0.0:14541"
        )

        print("Waiting for heartbeat...")
        master.wait_heartbeat()
        print("Heartbeat received")

        while self.running:

            msg = master.recv_match(blocking=True, timeout=1)

            if msg is None:
                continue

            msg_type = msg.get_type()

            with lock:

                #
                # Relative altitude, speed, heading
                #
                if msg_type == "GLOBAL_POSITION_INT":

                    latest_data["altitude"] = msg.relative_alt / 1000.0
                    latest_data["heading"] = msg.hdg / 100.0

                #
                # Ground speed
                #
                elif msg_type == "VFR_HUD":

                    latest_data["speed"] = msg.groundspeed

                #
                # GPS
                #
                elif msg_type == "GPS_RAW_INT":

                    latest_data["latitude"] = msg.lat / 1e7
                    latest_data["longitude"] = msg.lon / 1e7
                    latest_data["gps_altitude"] = msg.alt / 1000.0
                    latest_data["gps_fix"] = msg.fix_type
                    latest_data["satellites"] = msg.satellites_visible

    def stop(self):
        self.running = False


class DrawDynamicText:

    def __init__(self,  name="PyMAVLink Telemetry Overlay"):
        self.frame_number = 0
        self.receiver = MavlinkReceiver()
        self.receiver.start()
        self.name = name

    def process_frame(self, frame: VideoFrame):

        self.frame_number += 1

        with lock:

            altitude = latest_data["altitude"]
            speed = latest_data["speed"]
            heading = latest_data["heading"]

            latitude = latest_data["latitude"]
            longitude = latest_data["longitude"]
            gps_altitude = latest_data["gps_altitude"]
            gps_fix = latest_data["gps_fix"]
            satellites = latest_data["satellites"]

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

        width = frame.video_info().width
        height = frame.video_info().height

        #
        # Add a small ROI in the upper-left corner.
        # gvawatermark draws the ROI label.
        #
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
