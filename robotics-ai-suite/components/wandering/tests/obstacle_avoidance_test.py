#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Test module for obstacle avoidance functionality."""

import logging
import os
import shutil
import signal
import subprocess  # nosec B404
import time
from pathlib import Path
import numpy as np
import pytest
from PIL import Image


def _resolve_binary(name):
    """Return absolute path to executable ``name`` or raise if not found on PATH."""
    path = shutil.which(name)
    if path is None:
        raise FileNotFoundError(f"Required executable '{name}' was not found on PATH")
    return path


DEFAULT_RESOLUTION = '1680x1050x24'
DEFAULT_DISPLAY = ':10.0'

DIFF_SIZE_BYTES_THRESHOLD = 2000
DIFF_THRESHOLD_PERCENTAGE = 0.0059


def take_screenshot_series(screenshot_dir, screenshot_name_prefix="screenshot_", display=":10.0",
                           frame_rate=1, record_time=1):
    """
    Capture a series of screenshots from the specified X display using ffmpeg.

    Args:
        screenshot_dir (str): Directory to save screenshots.
        screenshot_name_prefix (str): Prefix for screenshot filenames.
        display (str): X display to capture from.
        frame_rate (int): Frame rate for screenshot capture.
        record_time (int): Duration in seconds to record screenshots.
    """
    os.makedirs(screenshot_dir, exist_ok=True)

    # Resolve the X display geometry in Python instead of via a shell pipeline so
    # ffmpeg can be launched with an argv list (avoids shell=True).
    xdpyinfo = _resolve_binary("xdpyinfo")
    xdpyinfo_env = {**os.environ, "DISPLAY": display}
    xdpyinfo_result = subprocess.run(  # nosec B603
        [xdpyinfo], capture_output=True, text=True, check=True, env=xdpyinfo_env
    )
    video_size = ""
    for line in xdpyinfo_result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("dimensions:"):
            # Format: "dimensions:    1680x1050 pixels (445x278 millimeters)"
            video_size = stripped.split()[1]
            break
    if not video_size:
        raise RuntimeError(f"Unable to determine display dimensions for {display}")

    ffmpeg = _resolve_binary("ffmpeg")
    output_pattern = os.path.join(
        screenshot_dir, f"{screenshot_name_prefix}_%06d.png"
    )
    cmd = [
        ffmpeg, "-y", "-f", "x11grab", "-video_size", video_size,
        "-i", display, "-r", str(frame_rate), output_pattern,
    ]
    with subprocess.Popen(cmd, start_new_session=True) as process:  # nosec B603
        time.sleep(record_time)
        terminate_process_gracefully(process)


def is_same_image(img_ref: str, img_result: str, pixel_threshold=DIFF_THRESHOLD_PERCENTAGE,
                  fail_on_size=True):
    """
    Compare two images and determine if they are the same or very similar.

    Args:
        img_ref (str): Path to the reference image.
        img_result (str): Path to the result image.
        pixel_threshold (float): Threshold for pixel difference percentage.
        fail_on_size (bool): Whether to fail if image sizes differ significantly.

    Returns:
        bool: True if images are the same or very similar, False otherwise.
    """

    logging.info("Comparing image: '%s' to image '%s'", img_ref, img_result)

    reference_image = Image.open(img_ref)
    result_image = Image.open(img_result)

    if (reference_image.mode != result_image.mode) or (reference_image.size != result_image.size) \
            or (reference_image.getbands() != result_image.getbands()):
        logging.error("There are differences between images (different picture size/mode/band) !!")
        return False

    # if img size larger than DIFF_SIZE_BYTES_THRESHOLD bytes fail
    size_diff = abs(os.path.getsize(img_ref) - os.path.getsize(img_result))
    if size_diff > DIFF_SIZE_BYTES_THRESHOLD:
        logging.error("There is more than %s bytes difference between image sizes "
                      "on disk: %s!", DIFF_SIZE_BYTES_THRESHOLD, size_diff)
        if fail_on_size:
            logging.debug("Failing because of difference in physical disk picture size")
            return False

    try:
        pairs = zip(reference_image.getdata(), result_image.getdata())
        # compare non-grey images
        diff_percentage = sum(abs(c1 - c2) for p1, p2 in pairs for c1, c2 in zip(p1, p2))

        ncomponents = result_image.size[0] * result_image.size[1] * 3
        percentage = (diff_percentage / 255.0 * 100) / ncomponents

        if percentage >= pixel_threshold:
            logging.error("Images differ with percentage: %s while threshold is:"
                          " %s... !!", percentage, pixel_threshold)
            return False
    except Exception as e:
        logging.error("Image comparison error: %s", str(e))
        raise
    logging.info("Images are the same or very very similar")
    return True


def start_ros_bag_playback(bag_path, loop=False):
    """Start ROS bag playback as a background process.

    Args:
        bag_path: path to the ROS bag file or directory
        loop: whether to loop the bag playback

    Returns:
        subprocess.Popen: The started process
    """
    cmd = [_resolve_binary("ros2"), "launch", "wandering_gazebo_tutorial", bag_path]
    if loop:
        cmd.append("--loop")

    return subprocess.Popen(  # nosec B603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )


def terminate_process_gracefully(process):
    """Terminate the given process group gracefully, then forcefully if needed.

    Args:
        process: subprocess.Popen object to terminate
    """
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGINT)
    except ProcessLookupError:
        # Process already exited
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def start_virtual_display(display=DEFAULT_DISPLAY,
                          resolution=DEFAULT_RESOLUTION):
    """Start Xvfb virtual display for headless GUI testing.

    Args:
        display: X display number to use
        resolution: display resolution in format WIDTHxHEIGHTxDEPTH

    Returns:
        subprocess.Popen: The started Xvfb process
    """
    return subprocess.Popen(  # nosec B603
        [_resolve_binary("Xvfb"), f"{display}", "-ac", "-screen", "0", resolution],
        start_new_session=True
    )


def mask_image_numpy(image_path, mask_path, masked_path):
    """
    Apply a mask to an image and save the result.

    Args:
        image_path (str): Path to the source image.
        mask_path (str): Path to the mask image.
        masked_path (str): Path to save the masked image.
    """
    logging.debug(
        "Applying mask: '%s' on image: '%s' and saving to: '%s' ",
        mask_path, image_path, masked_path
    )
    src = np.array(Image.open(image_path))
    mask = np.array(Image.open(mask_path).resize(src.shape[1::-1], Image.BILINEAR))
    # mask
    mask = mask / 255
    # the mask needs to be exported as rgb 8 bit only values, no alpha
    dst = src * mask
    img = Image.fromarray(dst.astype(np.uint8))
    img.save(masked_path)


def wait_for_gazebo_world(gazebo_log_path, max_retries=8, sleep_duration=60):
    """Wait for Gazebo to load the world file."""
    for attempt in range(max_retries):
        try:
            if os.path.exists(gazebo_log_path):
                with open(gazebo_log_path, 'r', encoding='utf-8') as log_file:
                    log_content = log_file.read()
                    if 'Loading world' in log_content:
                        return True
            time.sleep(sleep_duration)
        except (IOError, OSError) as e:
            pytest.fail(f"Error accessing Gazebo log file: {e}")

        if attempt == max_retries - 1:
            pytest.fail(
                f"Timeout: Gazebo did not load world file after "
                f"{max_retries * sleep_duration} seconds"
            )
    return False


def mask_and_check_collisions(captured_images, out_dir, mask_image, reference_masked_gazebo):
    """Mask images and check for possible collisions."""
    masked_screenshots_full_path = os.path.join(out_dir, "masked_screenshots_series")
    os.makedirs(masked_screenshots_full_path)
    found_possible_collision = False
    for img_item in captured_images:
        if img_item.is_file():
            if not found_possible_collision:
                filtered_image = os.path.join(
                    masked_screenshots_full_path, img_item.parts[-1:][0]
                )
                mask_image_numpy(img_item, mask_image, filtered_image)
                if not is_same_image(filtered_image, reference_masked_gazebo, 1.2, False):
                    pytest.fail(
                        (
                            f"Masked image: '{filtered_image}' seems to detect collision, "
                            f"please also investigate using the captured image: "
                            f"'{img_item.as_posix()}'"
                        )
                    )
                    found_possible_collision = True
                    continue

                os.remove(filtered_image)
                os.remove(img_item)
            else:
                os.remove(img_item)
    if found_possible_collision:
        pytest.fail("Possible collision detected during obstacle avoidance test.")


@pytest.fixture(name="after", autouse=True)
def after_fixture():
    """Copy Gazebo log file after each test run for debugging purposes."""
    yield
    gazebo_log = Path("/root/.gazebo/server-11345/default.log")
    target_dir = Path("testout")
    try:
        if gazebo_log.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(gazebo_log, target_dir / gazebo_log.name)
    except (FileNotFoundError, PermissionError, OSError) as exc:
        logging.warning("Failed to copy Gazebo log %s: %s", gazebo_log, exc)


def test_obstacle_avoidance():  # pylint: disable=too-many-locals
    """Test obstacle avoidance in Gazebo simulation."""

    os.environ["DISPLAY"] = ":10.0"
    os.environ["ROS_DOMAIN_ID"] = "1"

    xvfb_process = None
    fluxbox_process = None
    launch_process = None

    os.makedirs("testout", exist_ok=True)

    try:
        xvfb_process = start_virtual_display(display=":10.0")
        # pylint: disable=R1732
        fluxbox_process = subprocess.Popen(  # nosec B603
            [_resolve_binary("fluxbox")],
            start_new_session=True
        )
        launch_process = subprocess.Popen(  # nosec B603
            [_resolve_binary("ros2"), "launch", "wandering_gazebo_tutorial",
             "wandering_gazebo.launch.py"],
            stdout=open("testout/obstacle_avoidance_test_launch.log", "w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
        # pylint: enable=R1732

        gazebo_log_path = "/root/.gazebo/server-11345/default.log"
        wait_for_gazebo_world(gazebo_log_path)

        # make sure Gazebo initializes properly
        time.sleep(120)

        # Locate the Gazebo X11 window and resize/move it to a known geometry.
        # Originally a single shell pipeline; refactored to argv-list calls so
        # subprocess is invoked without shell=True.
        x11_env = {**os.environ, "DISPLAY": ":10.0"}
        xwininfo = _resolve_binary("xwininfo")
        xdotool = _resolve_binary("xdotool")
        wmctrl = _resolve_binary("wmctrl")

        xwininfo_result = subprocess.run(  # nosec B603
            [xwininfo, "-root", "-tree"],
            capture_output=True, text=True, check=True, env=x11_env,
        )
        window_id = None
        for line in xwininfo_result.stdout.splitlines():
            if "Gazebo" in line:
                window_id = line.strip().split()[0]
                break
        if not window_id:
            pytest.fail("Unable to locate Gazebo window in xwininfo output")
        logging.info("window id=%s", window_id)

        for xdotool_args in (
            [xdotool, "windowfocus", "--sync", window_id],
            [xdotool, "windowsize", "--sync", window_id, "90%", "100%"],
            [xdotool, "windowmove", "--sync", window_id, "0", "0"],
        ):
            subprocess.run(  # nosec B603
                xdotool_args, check=True, env=x11_env,
            )
        subprocess.run(  # nosec B603
            [wmctrl, "-ir", window_id, "-e", "0,0,0,1510,1010"],
            check=True, env=x11_env,
        )

        out_dir = "testout/screenshots/"
        take_screenshot_series(
            out_dir,
            screenshot_name_prefix="gazebo_test_",
            frame_rate=20,
            record_time=360,
        )

        captured_images = sorted(Path(out_dir).iterdir())
        if not captured_images:
            pytest.fail("No screenshots captured.")

        first_img = captured_images[0].as_posix()
        last_img = captured_images[-1].as_posix()

        if not os.path.exists(first_img) or os.path.getsize(first_img) == 0:
            pytest.fail(f"First image {first_img} does not exist or is empty.")

        if not os.path.exists(last_img) or os.path.getsize(last_img) == 0:
            pytest.fail(f"Last image {last_img} does not exist or is empty.")

        if is_same_image(first_img, last_img):
            logging.error("Robot does not seem to have moved, failing ...")
            pytest.fail("Robot does not seem to have moved.")
        logging.info("Robot seems to have moved ...")

        mask_image_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "assets",
            "gazebo_mask.png"
        )
        reference_masked_gazebo = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "assets",
            "masked_gazebo.png"
        )
        mask_and_check_collisions(
            captured_images,
            out_dir,
            mask_image_path,
            reference_masked_gazebo
        )

    finally:
        for process in [launch_process, fluxbox_process, xvfb_process]:
            if process is not None:
                terminate_process_gracefully(process)
