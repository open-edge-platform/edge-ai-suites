import argparse

from da import config
from da.util.log import logger


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate video from keyboard inputs text.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--avatar_id",
        "-ai",
        type=str,
        default="my-avatar",
        help="Id for avatar loaded."
    )

    parser.add_argument(
        "--output_prefix",
        "-o",
        type=str,
        default="my-avatar",
        help="The prefix for output video files."
    )

    parser.add_argument(
        "--male_voice",
        "-m",
        action='store_true',
        default=False,
        help="Use male voice in generated video, use female voice if not present."
    )

    parser.add_argument(
        "--fps",
        "-f",
        type=int,
        default=24,
        help="The FPS of generated video."
    )

    return parser.parse_args()


def main():
    args = parse_args()

    from da.avatar2d.avatar_ov import AvatarOV
    from da.speak.tts_client import TTSClient
    from da.util.video_writer import encode_video

    # Load avatar.
    batch_size = 4
    avatar = AvatarOV(
        avatar_id=args.avatar_id,
        video_path="",
        bbox_shift=0,
        batch_size=batch_size,
        preparation=False,
        fps=args.fps,
        ov_device=config.ov.device,
    )

    logger.info("avatar loaded.")

    # load tts model
    tts_client = TTSClient(args.male_voice)

    output_idx = 0
    while True:
        output_idx += 1

        speak_text = input("请输入文本：")
        if speak_text == "exit":
            break

        if speak_text == "":
            continue

        audio_path = tts_client.tts(speak_text)
        frames = avatar.inference(audio_path, 25)
        encode_video(audio_path, frames, f"output/video/{args.output_prefix}-{output_idx}.mp4", 25)


if __name__ == '__main__':
    main()
