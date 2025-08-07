:orphan:

.. recorder-tool:

Recorder tool
=====================================

This tutorial will show you how to use the recorder tool to efficiently store video topics using encode and decode.

Installation
--------------

   .. code-block:: bash

      sudo apt install ros-humble-recorder
      # (optionally) install also a bag for purpose of demonstration
      sudo apt install ros-humble-bagfile-2d-lidar

Configuration
--------------

First, you need to set up ``config.toml`` file, below is an example of a configuration file.
You can configure it to suit your needs.

   .. code-block:: toml

      [main]
      topics = ["camera1" ,"camera1_depth_qoi"] # list of topics, must match the section names
      save_dir = "./saved_videos" # folder where the videos will be saved

      [Player]
      buffer_size = 50 # number of frames to read ahead
      loop = false # if false, will exit when reaching the end of the video

      [FFMpegVideoEncoder]
      # If you do not know what your are doing, do not change these values
      ffmpeg_play_string = "ffmpeg -init_hw_device vaapi -hwaccel_output_format vaapi -re  -hwaccel auto -i <filename> -vf 'hwdownload,format=nv12' -c:v h264_vaapi -f image2pipe -pix_fmt rgb24 -vcodec rawvideo - "
      ffmpeg_record_string   = "ffmpeg -y -init_hw_device vaapi -loglevel verbose -f rawvideo -pix_fmt rgb24 -s <resolution> -r <fps> -i - -vf 'format=nv12,hwupload' -c:v h264_vaapi <filename> "

      # Define topics to record
      # Name of the section is not important
      # topic - string; its's just the ros topic it will subscribe to
      # encoding - string rgb8 or 16UC1; are currently supported
      # expected_fps - integer, expected fps of the topic, used to pace the saved video (required for ffmpeg)
      # encoder - string ffmpeg or qoi; (ffmpeg is lossy and uses hw acceleration, qoi is lossless and uses cpu)
      # scale_factor - integer; when using qoi it's possible to scale down the image to save space, 1 means no scaling, 2 means 1/4 of the original size, 4 means 1/16 of the original size

      [camera1]
      topic = "/camera/color/image_raw"
      expected_fps = 15
      encoding = "rgb8"
      encoder = "ffmpeg"

      [camera1_depth_qoi]
      topic = "/camera/aligned_depth_to_color/image_raw"
      expected_fps = 15
      encoding = "16UC1"
      scale_factor = 1
      encoder = "qoi"


Usage - recording
-------------------

To start recording, first, start the ``ros2 bag`` tool. Feel free to use it to record all the topics you want to record. Importantly, you will need to record the topics produced by the recorder tool, that is ``/camera/color/image_raw_dummy`` and ``/camera/aligned_depth_to_color/image_raw_dummy``. These names are created by adding ``_dummy`` to the original topic names and they are used to synchronize with bag and store metadata.

Run the following commands in separate terminals.

   .. code-block:: bash

      ros2 bag record -o lidar2d_bag /parameter_events /scan /rosout /camera/color/camera_info /camera/aligned_depth_to_color/camera_info /tf /tf_static /camera/aligned_depth_to_color/image_raw_dummy /camera/color/image_raw_dummy

Then start the recorder tool.

   .. code-block:: bash

      ros2 run recorder recorder_node --ros-args -p toml:="./config.toml" -p mode:=record   

Finally, run the load you want to record. This time we are going to use the pre-recorded bag file. However, you can use your own video streams like cameras and so on.

   .. code-block:: bash

      ros2 bag play /opt/ros/humble/share/bagfiles/2d-lidar   

After the bag finishes playing, stop the recorder tool and bag tool, by pressing ``Ctrl+C``.

Usage - playback
--------------------

Run the following commands in separate terminals.

To playback the recorder video, first start the recorder tool.

   .. code-block:: bash

      ros2 run recorder recorder_node --ros-args -p toml:="./config.toml" -p mode:=play

Then start the ``ros2 bag`` tool.

   .. code-block:: bash

      ros2 bag play lidar2d_bag

Also, feel free to start the rviz2 tool to visualize the video.

   .. code-block:: bash

      rviz2 

Additional notes
-----------------

By tweaking the configuration of ``FFMpegVideoEncoder`` section you can change codec and it's parameters. Supported codecs : https://www.intel.com/content/www/us/en/docs/onevpl/developer-reference-media-intel-hardware/1-1/overview.html

Expected frame rate should roughly match the actual frame rate of the topic. Else, during playback, there might be a mismatch between framerate produced by ffmpeg and the requested framerate.

This tool is most useful when ffmpeg is used to encode all topics as this can provide 100x smaller file sizes than using standard bag files.

