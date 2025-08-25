std_msgs/Header header # Header timestamp should be acquisition time of image

sensor_msgs/Image rgb_image
sensor_msgs/Image depth_image

string task # "Dectection" "Segmentation "Pose" 

geometry_msgs/TransformStamped camera_transform

YoloDetection[] detections