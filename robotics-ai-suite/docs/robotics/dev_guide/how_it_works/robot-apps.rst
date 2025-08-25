|p_amr| Applications
---------------------


-  **The Wandering Application**, included in the |p_amr|, demonstrates the
   combination of the middleware, algorithms, and the |ros| navigation stack. It showcases the
   ability to navigate a robot to explore an unknown environment, avoiding hitting obstacles, updating a local
   map in real-time exposed as a ROS topic, and publishing AI objects
   detected in another ROS topic (It uses the robot's sensors and actuators based on its hardware configuration.)

-  **Object Detection AI Application**, detects objects in video data using a deep
   learning neural network model from the |openvino| `Model Zoo <https://docs.openvino.ai/2023.2/model_zoo.html>`__

-  **Semantic Segmentation AI Application**, is a computer vision application that assigns labels to each pixel according to the object it belongs to, 
   creating so-called segmentation masks.

-  **Ground Floor Segmentation Application**, uses pointcloud data for distinguishing between ground floor, 
   elevated surfaces, obstacles, and structures above ground level.

-  **Benchmarking Application**, is a toolkit that uses the |lp_amr| ingredients to run various combinations of Robotic application & AI application to estimate robotics and 
   deep learning inference performances respectively on supported devices.
