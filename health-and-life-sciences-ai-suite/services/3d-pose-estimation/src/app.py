import cv2
import argparse

from inference import PoseEstimator
from pose_encoder import encode_pose_frame
from publisher import PoseGrpcPublisher


def main(video_source, grpc_addr):
    estimator = PoseEstimator()
    publisher = PoseGrpcPublisher(grpc_addr)

    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        raise RuntimeError("❌ Cannot open video source")

    print(f"✅ 3D Pose streaming to gRPC @ {grpc_addr}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        raw_outputs = estimator.infer(frame)
        pose_frame = encode_pose_frame(raw_outputs)

        publisher.send(pose_frame)

    cap.release()
    publisher.close()
    print("🛑 Pose service stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="videos/face-demographics-walking.mp4")
    parser.add_argument("--grpc", default="localhost:50051")
    args = parser.parse_args()

    video_src = int(args.video) if str(args.video).isdigit() else args.video
    main(video_src, args.grpc)
