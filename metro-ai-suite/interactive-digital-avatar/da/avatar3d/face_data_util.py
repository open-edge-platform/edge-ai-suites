import copy

import numpy as np

face_channels = [
    "noseSneerRight",
    "noseSneerLeft",
    "cheekSquintRight",
    "cheekSquintLeft",
    "cheekPuff",
    "jawOpen",
    "jawRight",
    "jawLeft",
    "jawForward",
    "browOuterUpRight",
    "browOuterUpLeft",
    "browInnerUp",
    "browDownRight",
    "browDownLeft",
    "mouthStretchRight",
    "mouthStretchLeft",
    "mouthFrownRight",
    "mouthFrownLeft",
    "mouthDimpleRight",
    "mouthDimpleLeft",
    "mouthSmileRight",
    "mouthSmileLeft",
    "mouthPressRight",
    "mouthPressLeft",
    "mouthUpperUpLeft",
    "mouthUpperUpRight",
    "mouthLowerDownRight",
    "mouthLowerDownLeft",
    "mouthShrugLower",
    "mouthShrugUpper",
    "mouthRollLower",
    "mouthRollUpper",
    "mouthFunnel",
    "mouthPucker",
    "mouthLeft",
    "mouthRight",
    "mouthClose",
    "eyeWideRight",
    "eyeWideLeft",
    "eyeSquintRight",
    "eyeSquintLeft",
    "eyeLookUpRight",
    "eyeLookUpLeft",
    "eyeLookOutRight",
    "eyeLookOutLeft",
    "eyeLookInRight",
    "eyeLookInLeft",
    "eyeLookDownRight",
    "eyeLookDownLeft",
    "eyeBlinkRight",
    "eyeBlinkLeft"
]


def npy_to_face_pose(datas: np.array) -> list[dict]:
    arkit_info_template = {"face_data": {"Parameter": []}}
    for name in face_channels:
        arkit_info_template["face_data"]['Parameter'].append({"Name": name, "Value": 0.0})

    face_frames = [arkit_info_template, ]

    for i in range(datas.shape[0]):
        arkit_info = copy.deepcopy(arkit_info_template)
        for j in range(datas.shape[1]):
            arkit_info['face_data']['Parameter'][j]['Value'] = float(datas[i][j])
        face_frames.append(arkit_info)

    face_frames.append(arkit_info_template)

    return face_frames


mouth_key = {
    'jawForward',
    'jawLeft',
    'jawRight',
    'jawOpen',
    'mouthClose',
    'mouthFunnel',
    'mouthPucker',
    'mouthLeft',
    'mouthRight',
    'mouthSmileLeft',
    'mouthSmileRight',
    'mouthFrownLeft',
    'mouthFrownRight',
    'mouthDimpleLeft',
    'mouthDimpleRight',
    'mouthStretchLeft',
    'mouthStretchRight',
    'mouthRollUpper',
    'mouthRollLower',
    'mouthShrugLower',
    'mouthShrugUpper',
    'mouthPressLeft',
    'mouthPressRight',
    'mouthLowerDownLeft',
    'mouthLowerDownRight',
    'mouthUpperUpLeft',
    'mouthUpperUpRight'
}


def merge_mouth_json(x: dict, y: dict) -> dict:
    for i in range(len(x["face_data"]["Parameter"])):
        if x["face_data"]["Parameter"][i]["Name"] in mouth_key:
            x["face_data"]["Parameter"][i]["Value"] = y["face_data"]["Parameter"][i]["Value"]

    return x


said_order = [
    'eyeBlinkLeft',
    'eyeLookDownLeft',
    'eyeLookInLeft',
    'eyeLookOutLeft',
    'eyeLookUpLeft',
    'eyeSquintLeft',
    'eyeWideLeft',
    'eyeBlinkRight',
    'eyeLookDownRight',
    'eyeLookInRight',
    'eyeLookOutRight',
    'eyeLookUpRight',
    'eyeSquintRight',
    'eyeWideRight',
    'jawForward',
    'jawLeft',
    'jawRight',
    'jawOpen',
    'mouthClose',
    'mouthFunnel',
    'mouthPucker',
    'mouthLeft',
    'mouthRight',
    'mouthSmileLeft',
    'mouthSmileRight',
    'mouthFrownLeft',
    'mouthFrownRight',
    'mouthDimpleLeft',
    'mouthDimpleRight',
    'mouthStretchLeft',
    'mouthStretchRight',
    'mouthRollUpper',
    'mouthRollLower',
    'mouthShrugLower',
    'mouthShrugUpper',
    'mouthPressLeft',
    'mouthPressRight',
    'mouthLowerDownLeft',
    'mouthLowerDownRight',
    'mouthUpperUpLeft',
    'mouthUpperUpRight',
    'browDownLeft',
    'browDownRight',
    'browInnerUp',
    'browOuterUpLeft',
    'browOuterUpRight',
    'cheekPuff',
    'cheekSquintLeft',
    'cheekSquintRight',
    'noseSneerLeft',
    'noseSneerRight'
]

said_order_to_face_channels_index = [said_order.index(name) for name in face_channels]


def said_order_to_render_order(said_order_data):
    return said_order_data[:, said_order_to_face_channels_index]
