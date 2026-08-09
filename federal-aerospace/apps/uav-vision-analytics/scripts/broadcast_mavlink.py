import socket
from pymavlink import mavutil

INPUT_PORT = 14550
OUTPUT_PORT = 14541
BROADCAST_IP = "255.255.255.255"

# Receive MAVLink
mav = mavutil.mavlink_connection(
    f"udpin:0.0.0.0:{INPUT_PORT}"
)

# UDP broadcaster
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

print(f"Listening for MAVLink on :{INPUT_PORT}")
print(f"Broadcasting MAVLink on {BROADCAST_IP}:{OUTPUT_PORT}")

while True:
    msg = mav.recv_match(blocking=True)

    if msg is None:
        continue

    # Convert the decoded MAVLink message back to wire format
    packet = msg.get_msgbuf()

    if packet:
        sock.sendto(packet, (BROADCAST_IP, OUTPUT_PORT))
