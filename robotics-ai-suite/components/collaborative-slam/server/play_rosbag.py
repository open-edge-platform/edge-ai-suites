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
Usage: ./play_rosbag.py xxx.bag [rosbag play options (--topics not supported) ]
optional options: use_sim_time =1  keep_time=1
use_sim_time =1 : use recorded time
use_sim_time =0 : use current time
keep_time = 1: keep relative timestamp between msgs
keep_time = 0: do not keeping relative timestamp between msgs
If you choose not to use use_sim_time=0, you also have to choose whether to keep relative timestamp between msgs(set keep_time= 0 or 1)
But it you choose to use use_sim_time=1, you don't need to set keep_time
if you are going to use IMU, odometry and other msgs which will be integrated by using time, you need to set keep_time=1
By Xuesong Shi, 2018
"""
import rospy
import rosbag
from functools import partial
import subprocess
import threading
import time
import sys
from tf2_msgs.msg import TFMessage
from sensor_msgs.msg import CameraInfo
import argparse
import copy

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
            msg.header.stamp = start_time + (msg.header.stamp - reset_stamp_keep_time.start_record_time)
        last_time = msg.header.stamp
    elif hasattr(msg, 'transforms'):
        last_tf_publish_time = last_time
        for id in range(len(msg.transforms)):
            if hasattr(msg.transforms[id], 'header') and hasattr(msg.transforms[id].header, 'stamp'):
                if msg.transforms[id].header.stamp.secs <= 0 :
                    msg.transforms[id].header.stamp = last_tf_publish_time
                else:
                    if not use_sim_time:
                        if hasattr(reset_stamp_keep_time, 'start_record_time'):
                            msg.transforms[id].header.stamp = start_time + (
                                    msg.transforms[id].header.stamp - reset_stamp_keep_time.start_record_time)
                        else:
                            reset_stamp_keep_time.start_record_time = msg.transforms[id].header.stamp
                            msg.transforms[id].header.stamp = start_time + (
                                    msg.transforms[id].header.stamp - reset_stamp_keep_time.start_record_time)
                            last_time = msg.transforms[id].header.stamp
                    else:
                        last_time = msg.transforms[id].header.stamp
            else:
                msg.transforms[id].header.stamp = last_tf_publish_time
    return msg


def reset_stamp(msg):
    global use_sim_time, last_time
    t = rospy.Time.now()
    if hasattr(msg, 'header') and hasattr(msg.header, 'stamp'):
        if not use_sim_time:
            msg.header.stamp = t
        else:
            last_time = msg.header.stamp
    elif hasattr(msg, 'transforms'):
        for id in range(len(msg.transforms)):
            if not use_sim_time:
                msg.transforms[id].header.stamp = t
            else:
                msg.transforms[id].header.stamp = last_time
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


def publish_loop(pub, msg, interval=0.02):
    time.sleep(3)
    print("start publish loop!")
    global keep_relative_time, last_time, last_tf_publish_time
    last_tf_publish_time = rospy.Time(0, 0)
    last_time = rospy.Time(0, 0)
    while running and not rospy.is_shutdown():
            lock_keep_relative_time.acquire()
            if keep_relative_time:
                lock_keep_relative_time.release()
                lock_publish_thread.acquire()
                if last_time.nsecs >0 :
                    if last_tf_publish_time.secs < last_time.secs or last_tf_publish_time.nsecs < last_time.nsecs:
                        pub.publish(reset_stamp_keep_time(msg))
                lock_publish_thread.release()
            else:
                lock_keep_relative_time.release()
                lock_publish_thread.acquire()
                pub.publish(reset_stamp(msg))
                lock_publish_thread.release()
    time.sleep(interval)


def main():
    global start_time, use_sim_time
    bagfile = sys.argv[1]
    print(bagfile)
    loop_static_tf = True
    loop_camera_info= True
    remappings = {}
    play_args = []
    global keep_relative_time
    for arg in sys.argv[2:]:
        if ':=' in arg:
            topics = arg.split(':=')
            remappings[topics[0]] = topics[1]
        elif 'keep_time' in arg:
            krt = arg.split('=')
            keep_relative_time = int(krt[1])
        elif "use_sim_time" in arg:
            krt = arg.split('=')
            use_sim_time = int(krt[1])
        else:
            play_args.append(arg)

    rospy.init_node("play_rosbag")
    start_time = rospy.Time.now()
    remap_prefix = "/rosbag"
    topics = rosbag.Bag(bagfile).get_type_and_topic_info()[1]
    publishers = {}
    subscribers = {}
    play_cmd = 'rosbag play ' + bagfile + ' ' + ' '.join(play_args)
    static_tf_msg = None
    camera_info_msg = None
    print ('Topics in ' + bagfile + ':')
    for topic in topics:
        print ('%s \t(%s)' % (topic, topics[topic].msg_type))
        # retrieve static tf
        if loop_static_tf and topic == '/tf_static':
            for topic, msg, t in rosbag.Bag(bagfile).read_messages('/tf_static'):
                if static_tf_msg is None:
                    static_tf_msg = msg
                else:
                    for transform in msg.transforms:
                        static_tf_msg.transforms.append(transform)
            if static_tf_msg is not None:
                print ('  ---> will loop %d static transforms on /tf' % len(msg.transforms))
                play_cmd += ' %s:=%s%s' % (topic, remap_prefix, topic)
                continue

        # retrieve camera_info message
        if loop_camera_info and topic == '/d400/color/camera_info':
            for topic, msg, t in rosbag.Bag(bagfile).read_messages('/d400/color/camera_info'):
                if camera_info_msg is None:
                    camera_info_msg = msg
            if camera_info_msg is not None:
                print (' will loop camera_info_msg ')
                continue

        # construct publisher
        msg_type = topics[topic].msg_type.split('/')
        # TODO implement a universal way to take care of remapping
        topic_remapped = topic if topic not in remappings else remappings[topic]
        cmd = 'from %s.msg import %s;\n' % (msg_type[0], msg_type[-1]) \
              + 'publishers[topic] = rospy.Publisher(topic_remapped, %s, queue_size=10)' % msg_type[-1]
        try:
            exec (cmd)
        except ImportError:
            print ('  ---> unknown type, skipped')
            continue
        if topic in remappings:
            print ('  ---> remap to %s' % remappings[topic])
        # define callback and subscriber
        cb = partial(publish_once, publishers[topic])
        cmd = 'subscribers[topic] = rospy.Subscriber(remap_prefix + topic, %s, cb)' % msg_type[-1]
        exec (cmd)
        # add remap option
        play_cmd += ' %s:=%s%s' % (topic, remap_prefix, topic)

    print ('\nStart to play... Press Ctrl+C to exit')
    if static_tf_msg is not None:
        if '/tf' not in publishers:
            publishers['/tf'] = rospy.Publisher('/tf', TFMessage, queue_size=10)
        static_tf_pub = threading.Thread(target=publish_loop, args=(publishers['/tf'], static_tf_msg))
        static_tf_pub.setDaemon(True)
        static_tf_pub.start()

    if camera_info_msg is not None:
        if '/camera_info' not in publishers:
            publishers['/camera_info'] = rospy.Publisher('/d400/color/camera_info', CameraInfo, queue_size=10)
        camera_info_pub = threading.Thread(target=publish_loop, args=(publishers['/camera_info'], camera_info_msg))
        camera_info_pub.setDaemon(True)
        camera_info_pub.start()

    p = subprocess.call(play_cmd, shell=True)
    if static_tf_msg is not None:
        global running
        running = False
        static_tf_pub.join()


if __name__ == "__main__":
    running = True
    lock_publish_thread = threading.Lock()
    lock_keep_relative_time = threading.Lock()
    main()
