
.. _realsense_node:

Realsense node
==============

The vision launcher automatically spawns all the component of the container, and it accept the following parameters

- namespace. By default `ipc`.

.. note:: 

    Changing namespace will change the search of a special file d415camera<newnamespace>, which has to exists.
    this file can be created under <rvc_dynamic_controller_use_caseinstallpath>/cameraurdf/
    Of course, if vision has a non default namespace, rvc_control has to have the same namespace, and when launching it
    the issue will be apparent.

- camera_name: by default `camera`
- rs_serial: by default null string. in case there are multiple cameras, the one to use is specified with this parameters


In addition to command line parameters, an yaml file is provided with default values, in ``<rvc_vision_main_install_path>/config/rs_parameters>``

The list is long and full of interesting parameters, useful to fine tune according to lightning, distance, camera perfomance enable_auto_white_balance
but standing out are:

- auto_exposure for both RGB and DEPTH streams:
    it might be usefull to set it to false, and manually fixing the exposure to a not so dark image but this will give
    constant frame rate (autoexposure FPS is dependent of illumination conditions).
- resolution and FPS parameters for both RGB and DEPTH streams



.. code-block:: yaml

    accel_fps: 0
    align_depth.enable: true
    allow_no_texture_points: false
    calib_odom_file: ''
    clip_distance: -0.8
    colorizer.enable: false
    config_file: ''
    decimation_filter.enable: false
    depth_module.emitter_enabled: 1
    depth_module.laser_power: 360.0
    depth_module.enable_auto_exposure: true
    depth_module.enable_auto_white_balance: true
    depth_module.exposure: 6000
    depth_module.exposure.1: 6000
    depth_module.exposure.2: 6000
    depth_module.gain.1: 16
    depth_module.gain.2: 16
    depth_module.profile: 640x480x30
    device_type: ''
    diagnostics_period: 0.0
    enable_accel: false
    enable_color: true
    enable_confidence: false
    enable_depth: true
    enable_fisheye1: false
    enable_fisheye2: false
    enable_gyro: false
    enable_infra1: false
    enable_infra2: false
    enable_pose: false
    enable_sync: true
    gyro_fps: 0
    infra_rgb: false
    initial_reset: false
    json_file_path: ''
    linear_accel_cov: 0.01
    log_level: info
    output: screen
    color_info_qos: "SENSOR_DATA"
    color_qos: "SENSOR_DATA"
    depth_info_qos: "SENSOR_DATA"
    depth_qos: "SENSOR_DATA"
    infra1_info_qos: "SENSOR_DATA"
    infra1_qos: "SENSOR_DATA"
    infra2_info_qos: "SENSOR_DATA"
    infra2_qos: "SENSOR_DATA"
    infra_info_qos: "SENSOR_DATA"
    infra_qos: "SENSOR_DATA"
    pointcloud.enable: true
    pointcloud.ordered_pc: true
    pointcloud.pointcloud_qos: "SENSOR_DATA"
    pointcloud.frames_queue_size: 1
    # 0: disable texture, 1: depth texture 2: RGB, see: https://intelrealsense.github.io/librealsense/doxygen/rs__sensor_8h.html#a01b4027af33139de861408872dd11b93a58a1d3d8a392aafe15b30b6d4575c153
    pointcloud.stream_filter: 2
    pointcloud.stream_index_filter: 0
    pose_fps: 200
    reconnect_timeout: 6.0
    rgb_camera.enable_auto_exposure: false
    rgb_camera.enable_auto_white_balance: true
    rgb_camera.exposure: 100
    rgb_camera.profile: 640x480x30
    rosbag_filename: ''
    #serial_no: _002422060415
    tf_publish_rate: 0.0
    topic_odom_in: ''
    tracking_module.profile: 0,0,0
    unite_imu_method: 0
    usb_port_id: ''
    wait_for_device_timeout: -1.0
