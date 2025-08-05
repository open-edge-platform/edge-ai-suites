#!/usr/bin/env python
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.
"""
Play a ROS bag with current time or the recorded time
Usage: ./play_rosbag_ros2.py xxx [ros2 bag play options (--topics not supported) ]
VIP: remember to change topics with your topic names of bag file in the code below
optional options: use_sim_time =1  keep_time=1
use_sim_time =1 : use recorded time
use_sim_time =0 : use current time
keep_time = 1: keep relative timestamp between msgs
keep_time = 0: do not keeping relative timestamp between msgs
If you choose not to use use_sim_time=0, you also have to choose whether to keep relative timestamp between msgs(set keep_time= 0 or 1)
But it you choose to use use_sim_time=1, you don't need to set keep_time
if you are going to use IMU, odometry and other msgs which will be integrated by using time, you need to set keep_time=1
"""
import rclpy
from rclpy.time import Time
import builtin_interfaces.msg

from sensor_msgs.msg import Image
from functools import partial
import subprocess
import threading
from threading import Thread
import sys
import copy

# Please change the topic names (type should not need to change) according to your setup
# TODO add automatic topic parser
topics = ['/d455_front/aligned_depth_to_color/image_raw', '/d455_front/color/image_raw', '/d455_rear/aligned_depth_to_color/image_raw', '/d455_rear/color/image_raw']
msg_type = ['sensor_msgs', 'Image']

CONVERSION_CONSTANT = 10 ** 9

start_time = 0
first_msg = 0
last_time = 0
keep_relative_time = 0
time_changed = 0
last_tf_publish_time = -1
use_sim_time = 0

def reset_stamp_keep_time(original_msg):
    global use_sim_time
    msg = copy.deepcopy(original_msg)
    global start_time, last_time, last_tf_publish_time
    if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
        if not use_sim_time:
            if not hasattr(reset_stamp_keep_time, 'start_record_time'):
                reset_stamp_keep_time.start_record_time = msg.header.stamp
            new_time = Time.from_msg(start_time).nanoseconds + (Time.from_msg(msg.header.stamp).nanoseconds - Time.from_msg(reset_stamp_keep_time.start_record_time).nanoseconds)
            msg.header.stamp = builtin_interfaces.msg.Time(sec=new_time // CONVERSION_CONSTANT, nanosec=new_time % CONVERSION_CONSTANT)
        last_time = msg.header.stamp
    return msg


def reset_stamp(msg):
    global use_sim_time, last_time
    # TODO find better way to get current time
    node = rclpy.create_node('tmp')
    t = node.get_clock().now().to_msg()
    if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
        if not use_sim_time:
            msg.header.stamp = t
        else:
            last_time = msg.header.stamp
    return msg


def publish_once(pub, msg):
    global keep_relative_time
    lock_keep_relative_time.acquire()
    if keep_relative_time:
         lock_keep_relative_time.release()
         lock_publish_thread.acquire()
         pub.publish(reset_stamp_keep_time(msg))
         lock_publish_thread.release()
    else:
        lock_keep_relative_time.release()
        lock_publish_thread.acquire()
        pub.publish(reset_stamp(msg))
        lock_publish_thread.release()


def main():
    global start_time, use_sim_time
    bagfile = sys.argv[1]
    print(bagfile)
    remappings = {}
    play_args = []
    global keep_relative_time
    for arg in sys.argv[2:]:
        if ':=' in arg:
            input_topics = arg.split(':=')
            remappings[input_topics[0]] = input_topics[1]
        if 'keep_time' in arg:
            krt = arg.split('=')
            keep_relative_time = int(krt[1])
        elif "use_sim_time" in arg:
            krt = arg.split('=')
            use_sim_time = int(krt[1])
        else:
            play_args.append(arg)

    rclpy.init()
    node = rclpy.create_node('play_rosbag')
    start_time = node.get_clock().now().to_msg()
    remap_prefix = "/rosbag"

    publishers = {}
    subscribers = {}
    play_cmd = 'ros2 bag play ' + bagfile + ' --remap ' + ' '.join(play_args)

    for topic in topics:
        # construct publisher
        # TODO implement a universal way to take care of remapping
        topic_remapped = topic if topic not in remappings else remappings[topic]
        # print(topic_remapped)
        cmd = 'from sensor_msgs.msg import Image;\n' \
              + 'publishers[topic] = node.create_publisher(Image, topic_remapped, 10)'
        try:
            exec (cmd)
        except ImportError:
            print ('  ---> unknown type, skipped')
            continue
        if topic in remappings:
            print ('  ---> remap to %s' % remappings[topic])
        # define callback and subscriber
        cb = partial(publish_once, publishers[topic])
        cmd = 'subscribers[topic] = node.create_subscription(Image, remap_prefix + topic, cb, 10)'
        exec (cmd)
        # add remap option
        # the original image data will now be published to remap_prefix + topic
        play_cmd += ' %s:=%s%s' % (topic, remap_prefix, topic)

    # whenever captured a msg under remap_prefix/topic (i.e. /rosbag/d455_front/color/image_raw)
    # deep copy the msg, change its timestamp and publish to topic (i.e. /d455_front/color/image_raw)
    spin_thread = Thread(target=rclpy.spin, args=(node,))
    spin_thread.start()

    print ('\nStart to play... Press Ctrl+C to exit')
    p = subprocess.call(play_cmd, shell=True)

    rclpy.shutdown()

if __name__ == "__main__":
    running = True
    lock_publish_thread = threading.Lock()
    lock_keep_relative_time = threading.Lock()
    main()
