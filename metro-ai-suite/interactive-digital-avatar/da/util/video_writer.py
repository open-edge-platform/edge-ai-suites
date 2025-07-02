from pathlib import Path

import cv2
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

from da.util.log import logger


def encode_video(audio_path, frames, video_name, fps):
    """
    Encodes a video from a list of OpenCV frames (NumPy arrays) and an audio file.

    Parameters:
        audio_path (str): Path to the audio file.
        frames (list): List of OpenCV frames in BGR (NumPy arrays).
        video_name (str): Name of the output video file (e.g., "output_video.mp4").
        fps (int): Frames per second for the video.
    """

    frames_rgb = [cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) for frame in frames]

    # Create a moviepy ImageSequenceClip from the list of frames
    clip = ImageSequenceClip(frames_rgb, fps=fps)

    # Load the audio file
    audio = AudioFileClip(audio_path)

    # Set the audio to the video clip
    video = clip.set_audio(audio)

    # Create parent dir
    Path(video_name).parent.mkdir(parents=True, exist_ok=True)

    # Export the video to a file
    video.write_videofile(video_name, codec="libx264", logger=None)

    logger.info(f"Video saved to {video_name}")
