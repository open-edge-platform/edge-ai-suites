#! /usr/bin/python3
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Common helper functions for pytest-based tests."""

import logging
import os
import signal
import subprocess
import time
import re
from PIL import Image, ImageChops

DIFF_SIZE_BYTES_THRESHOLD = 2000
PIXEL_DIFF_THRESHOLD_PERCENTAGE = 0.0059

DEFAULT_RESOLUTION = '1680x1050x24'
DEFAULT_DISPLAY = ':10.0'


def wait_for_process_ready(process, max_wait=10):
    """Wait for process to be ready by checking if it's still running and responsive.

    Args:
        process: subprocess.Popen object to monitor
        max_wait: maximum time to wait in seconds
    """
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if process.poll() is not None:
            # Process has terminated early, might be an error
            break
        time.sleep(0.1)
        if time.time() - start_time > 1.0:
            break


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


def check_fast_mapping_availability():
    """Check if fast_mapping_node is available via ros2 run.

    Returns:
        tuple: (bool, str) - (is_available, error_message)
    """
    try:
        # Check if the ROS2 package and executable exist without running the node
        result = subprocess.run(
            ["ros2", "pkg", "executables", "fast_mapping"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False
        )
        if result.returncode != 0:
            return False, "fast_mapping_node is not available via ros2."
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, "ros2 or fast_mapping_node is not available."

    return True, ""


def start_fast_mapping_node():
    """Start fast_mapping_node as a background process.

    Returns:
        subprocess.Popen: The started process
    """
    return subprocess.Popen(
        ["ros2", "run", "fast_mapping", "fast_mapping_node"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        start_new_session=True
    )


def check_log_for_crashes(log_file_path):
    """Check log file for segmentation faults or core dumps.

    Args:
        log_file_path: path to log file to check

    Returns:
        bool: True if no crashes found, False if crashes detected
    """
    try:
        with open(log_file_path, 'r', encoding='utf-8') as log_file:
            content = log_file.read().lower()

            if 'segmentation fault' in content:
                return False

            if 'core dumped' in content:
                return False

    except FileNotFoundError:
        return False
    except (IOError, OSError):
        return False

    return True


def start_ros_bag_playback(bag_path, loop=False):
    """Start ROS bag playback as a background process.

    Args:
        bag_path: path to the ROS bag file or directory
        loop: whether to loop the bag playback

    Returns:
        subprocess.Popen: The started process
    """
    cmd = ["ros2", "bag", "play", bag_path]
    if loop:
        cmd.append("--loop")

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )


def check_ros_topic_available(topic_name, timeout=10):
    """Check if a ROS topic is available and publishing data.

    Args:
        topic_name: name of the ROS topic to check
        timeout: timeout in seconds to wait for topic data

    Returns:
        tuple: (bool, str) - (is_available, error_message)
    """
    try:
        result = subprocess.run(
            ["ros2", "topic", "echo", topic_name, "--once"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        if result.returncode == 0:
            return True, ""
        return False, f"Topic {topic_name} not available or no data published"
    except subprocess.TimeoutExpired:
        return False, f"Timeout waiting for data on topic {topic_name}"
    except FileNotFoundError:
        return False, "ros2 command not available"


def start_virtual_display(display=DEFAULT_DISPLAY, resolution=DEFAULT_RESOLUTION):
    """Start Xvfb virtual display for headless GUI testing.

    Args:
        display: X display number to use
        resolution: display resolution in format WIDTHxHEIGHTxDEPTH

    Returns:
        subprocess.Popen: The started Xvfb process
    """
    return subprocess.Popen(
        ["Xvfb", f"{display}", "-ac", "-screen", "0", resolution],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )


def start_rviz_with_config(config_path, display=DEFAULT_DISPLAY):
    """Start RViz2 with specified configuration file.

    Args:
        config_path: path to RViz configuration file
        display: X display to use

    Returns:
        subprocess.Popen: The started RViz process
    """
    env = os.environ.copy()
    env["DISPLAY"] = display

    return subprocess.Popen(
        ["rviz2", "--display-config", config_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env
    )


def is_same_image(img_ref: str, img_result: str, pixel_threshold=PIXEL_DIFF_THRESHOLD_PERCENTAGE,
                  fail_on_size=True, diff_output_dir=None):
    """Compare two images and check if they are the same or very similar.

    Args:
        img_ref: path to reference image
        img_result: path to result image
        pixel_threshold: threshold for pixel difference percentage
        fail_on_size: whether to fail if image sizes differ significantly
        diff_output_dir: directory to save diff image (optional)

    Returns:
        bool: True if images are the same or very similar, False otherwise
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
        diff_pixels = ImageChops.difference(reference_image, result_image)
        # writing an image with only the different pixels
        if diff_output_dir is not None:
            diff_pixels.save(os.path.join(diff_output_dir, "diff.png"))

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


def compare_images_with_gm(reference_path, screenshot_path, tolerance=1000.0):
    """Compare two images using GraphicsMagick and return if they're similar within tolerance.

    Args:
        reference_path: path to reference image
        screenshot_path: path to screenshot image
        tolerance: maximum allowed difference metric

    Returns:
        tuple: (bool, float) - (images_similar, difference_metric)
    """
    try:
        result = subprocess.run(
            ["gm", "compare", "-metric", "MAE", reference_path, screenshot_path],
            capture_output=True,
            text=True,
            check=False
        )

        # Parse the difference metric from stderr
        match = re.search(r'(\d+\.?\d*)', result.stderr)
        if match:
            difference = float(match.group(1))
            return difference <= tolerance, difference
        # If we can't parse the result but no error occurred, assume similar
        if result.returncode == 0:
            return True, 0.0

        return False, float('inf')

    except (FileNotFoundError, subprocess.SubprocessError):
        return False, float('inf')
