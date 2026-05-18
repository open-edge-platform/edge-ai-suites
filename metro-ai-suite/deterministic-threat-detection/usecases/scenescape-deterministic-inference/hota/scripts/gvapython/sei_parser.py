from gi.repository import Gst
import json

START_CODE_3 = b'\x00\x00\x01'
START_CODE_4 = b'\x00\x00\x00\x01'

TARGET_UUID = bytes.fromhex("12345678123456781234567812345678")


def find_nals_avcc(data):
    i = 0
    n = len(data)

    while i + 4 <= n:
        nal_size = int.from_bytes(data[i:i+4], byteorder='big')
        i += 4

        if nal_size <= 0 or i + nal_size > n:
            break

        nal = data[i:i+nal_size]
        yield nal

        i += nal_size

def find_nals(data):
    i = 0
    n = len(data)

    while i < n:
        if data[i:i+4] == START_CODE_4:
            sc_len = 4
        elif data[i:i+3] == START_CODE_3:
            sc_len = 3
        else:
            i += 1
            continue

        i += sc_len
        start = i

        while i < n and data[i:i+4] != START_CODE_4 and data[i:i+3] != START_CODE_3:
            i += 1

        yield data[start:i]


def remove_emulation_prevention(data):
    out = bytearray()
    i = 0
    while i < len(data):
        if i + 2 < len(data) and data[i] == 0 and data[i+1] == 0 and data[i+2] == 3:
            out.extend([0, 0])
            i += 3
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def parse_sei(nal):
    rbsp = remove_emulation_prevention(nal[1:])  # skip nal header
    i = 0

    while i < len(rbsp):
        # payload type
        payload_type = 0
        while i < len(rbsp) and rbsp[i] == 0xFF:
            payload_type += 255
            i += 1
        if i >= len(rbsp):
            break
        payload_type += rbsp[i]
        i += 1

        # payload size
        payload_size = 0
        while i < len(rbsp) and rbsp[i] == 0xFF:
            payload_size += 255
            i += 1
        if i >= len(rbsp):
            break
        payload_size += rbsp[i]
        i += 1

        payload = rbsp[i:i+payload_size]
        i += payload_size

        if payload_type == 5 and len(payload) >= 20:
            uuid = payload[:16]
            if uuid == TARGET_UUID:
                frame_num = int.from_bytes(payload[16:20], byteorder='big')
                return frame_num

    return None


class ParseSEI:
    def __init__(self, stream_name):
        self.frame_count = 0
        self.stream_name = stream_name

    def process(self, frame):
        buffer = frame._VideoFrame__buffer

        success, mapinfo = buffer.map(Gst.MapFlags.READ)
        if not success:
            print(f"SEI failed to Decode")
            return True

        data = mapinfo.data

        frame_num = None

        for nal in find_nals_avcc(data):
            if len(nal) == 0:
                continue

            nal_type = nal[0] & 0x1F

            if nal_type == 6:  # SEI
                frame_num = parse_sei(nal)
                if frame_num is not None:
                    break

        buffer.unmap(mapinfo)

        if frame_num is not None:
            #pass
            print(f"[{self.stream_name}] Decoded SEI frame_num = {frame_num}")
            #frame.add_message(json.dumps({'frame_num': frame_num}))
        else:
            print("No SEI found to Decode")

        return frame_num

class SEIParser:
    def __init__(self, stream_name="qcam1"):
        self.parse_sei = ParseSEI(stream_name)

    def process(self, frame):
        frame_num = self.parse_sei.process(frame)
        frame.add_message(json.dumps({'sei_frame_num': frame_num}))
        return True
