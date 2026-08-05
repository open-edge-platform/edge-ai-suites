"""
Basler camera inference pipeline runner.

Usage:
    # Run inference pipeline only (no video output)
    GST_TRACERS="latency(flags=pipeline)" GST_DEBUG="GST_TRACER:7" \
    python3 app.py 2> /tmp/latency.log

    # Run full pipeline and save output video
    GST_TRACERS="latency(flags=pipeline)" GST_DEBUG="GST_TRACER:7" \
    python3 app.py filesink 2> /tmp/latency.log

Outputs:
    - filesink mode writes /tmp/output.avi
    - latency tracer logs are written to /tmp/latency.log
"""

import sys
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

Gst.init(None)

SERIAL = "24591747"
MODEL_XML = "./models/yolo11n.xml"
MODEL_PROC = "./models/yolo11_dlstreamer.json"

use_filesink = len(sys.argv) > 1 and sys.argv[1].lower() == "filesink"

if use_filesink:
    print("Running pipeline WITH filesink")

    pipeline_str = f"""
    gencamsrc serial={SERIAL} pixel-format=bayerrggb !
    bayer2rgb !
    videoscale !
    videoconvert !
    video/x-raw,width=1280,height=720,format=NV12 !
    gvadetect model={MODEL_XML} model-proc={MODEL_PROC} device=GPU threshold=0.5 !
    gvawatermark !
    videoconvert !
    jpegenc !
    avimux !
    filesink location=/tmp/output.avi
    """
else:
    print("Running pipeline WITHOUT filesink")

    pipeline_str = f"""
    gencamsrc serial={SERIAL} pixel-format=bayerrggb !
    bayer2rgb !
    videoscale !
    videoconvert !
    video/x-raw,width=1280,height=720,format=NV12 !
    gvadetect model={MODEL_XML} model-proc={MODEL_PROC} device=CPU threshold=0.5 !
    fakesink sync=false
    """

try:
    pipeline = Gst.parse_launch(pipeline_str)
except GLib.Error as e:
    print("Failed to create pipeline:")
    print(e)
    sys.exit(1)

bus = pipeline.get_bus()
bus.add_signal_watch()

loop = GLib.MainLoop()


def on_message(bus, message):
    msg_type = message.type

    if msg_type == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print("\nERROR:")
        print(err)

        if debug:
            print("\nDEBUG:")
            print(debug)

        loop.quit()

    elif msg_type == Gst.MessageType.EOS:
        print("End of stream")
        loop.quit()

    elif msg_type == Gst.MessageType.WARNING:
        warn, debug = message.parse_warning()
        print("\nWARNING:")
        print(warn)

        if debug:
            print("\nDEBUG:")
            print(debug)


bus.connect("message", on_message)

ret = pipeline.set_state(Gst.State.PLAYING)

if ret == Gst.StateChangeReturn.FAILURE:
    print("Failed to start pipeline")
    pipeline.set_state(Gst.State.NULL)
    sys.exit(1)

try:
    print("Pipeline running...")
    loop.run()

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    pipeline.set_state(Gst.State.NULL)
    print("Pipeline stopped")