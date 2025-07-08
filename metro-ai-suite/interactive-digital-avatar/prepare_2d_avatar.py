import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prepare a avatar characters from input video.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--video_path",
        "-v",
        type=str,
        default="input/video.mp4",
        help="Path to the input video file."
    )

    parser.add_argument(
        "--bbox_shift",
        "-b",
        type=int,
        default=0,
        help="Shift value for the bounding box. Controls the mouth opening, it is recommended to adjust for each video."
    )

    parser.add_argument(
        "--avatar_id",
        "-ai",
        type=str,
        default="my-avatar",
        help="Id for the avatar saved."
    )

    return parser.parse_args()


def main():
    from da.avatar2d.avatar import Avatar

    args = parse_args()
    batch_size = 4
    avatar = Avatar(
        avatar_id=args.avatar_id,
        video_path=args.video_path,
        bbox_shift=args.bbox_shift,
        batch_size=batch_size,
        preparation=True,
        fps=None
    )


if __name__ == "__main__":
    main()
