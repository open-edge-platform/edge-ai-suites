import time
import numpy as np
from proto.pose_pb2 import PoseFrame, PersonPose, Joint2D, Joint3D


def encode_pose_frame(raw_outputs, source_id="3d-pose-camera-01"):
    frame = PoseFrame()
    frame.timestamp_ms = int(time.time() * 1000)
    frame.source_id = source_id

    # Take first output tensor from the model
    output = np.asarray(raw_outputs[0])

    person = PersonPose()
    person.person_id = 0

    # Flatten all dimensions except the last one so that each
    # "kp" is a 1D vector of [x, y, z, (conf)]-like values.
    if output.ndim < 2:
        return frame

    num_features = output.shape[-1]
    keypoints = output.reshape(-1, num_features)

    # Model is expected to have up to 19 joints; cap to that
    max_joints = 19
    for kp in keypoints[:max_joints]:
        kp_flat = np.asarray(kp).ravel()
        if kp_flat.size < 3:
            continue

        x, y, z = float(kp_flat[0]), float(kp_flat[1]), float(kp_flat[2])
        conf = float(kp_flat[3]) if kp_flat.size > 3 else 1.0

        person.joints_2d.append(Joint2D(x=x, y=y))
        person.joints_3d.append(Joint3D(x=x, y=y, z=z))
        person.confidence.append(conf)

    frame.people.append(person)
    return frame
