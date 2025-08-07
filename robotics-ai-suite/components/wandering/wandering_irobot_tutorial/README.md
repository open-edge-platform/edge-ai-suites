# iRobot create 3 wandering tutorial

Tutorial for running the wandering app on the iRobot create 3 with
RealSense camera and Slamtec RPLidar with support for joystick and
keyboard control.

## iRobot web interface

Configure the robot using its web interface:

- ROS2 namespace (e.g. `/robot2`); this value gets passed to the launch file as argument `irobot_ns`,
- the NTP server,
- FastDDS as ROS DDS,
- the ethernet network,
- Discovery server address and port.

When the discovery server is used the `ROS_DOMAIN_ID` is not used.

## Intel board connected to iRobot

Install the `ros-humble-wandering-irobot-tutorial` package.

Start the discovery server in a new terminal:

```
fastdds discovery --server-id 0
```

or use the `systemd service` file provided by the tutorial package:

```
# One time setup
mkdir -p ~/.config/systemd/user
ln -s /opt/ros/humble/share/wandering_irobot_tutorial/systemd/fastdd-discovery.service ~/.config/systemd/user
systemctl --user daemon-reload

# Start the server after the setup
systemctl --user start fastdds-discovery.service
```

Set the environment variables for ROS2 to use the discovery server:

```
export ROS_DISCOVERY_SERVER=127.0.0.1:11811
export ROS_SUPER_CLIENT=true
unset ROS_DOMAIN_ID
```

Start the launch file using the namespace set on the robot:

```
ros2 launch wandering_irobot_tutorial wandering_irobot.launch.py irobot_ns:=/robot2
```

If the time is not synchronized messages could be dropped and the tutorial might fail.

To use `ros2 cli` utilities, e.g. `ros2 topic`, `ros2 node`, set the
environment variables above.
