

Vision Component Container
***************************


Preliminary steps:
==================

Before execution, there are some important steps to follow:

- Yolo model retrain
- objects pcd creation
- rvc_use_case_binaries package creation


Yolo model retrain
------------------

To retrain our yolo v5 model we followed `this tutorial <https://docs.ultralytics.com/yolov5/tutorials/train_custom_data>`_

then convert the model to openvino:

.. code-block:: bash

    python3 path/to/export.py --weights <retrainedmodel>.pt --include openvino


if there are troubles with this, follow `issue 5533 <https://github.com/ultralytics/yolov5/issues/5533>`_

PCD files creation
------------------

To create our PCD files, for two different setups we went through two different approces:

PCD file creation from 3D printable STL files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

 We created our set of object with a 3D modeler, 3D printed and then used the mesh files to created the pcd files :ref:`pose_detector` requires.

We used the tool obj2pcd offered in the libpcd tool ``pcl_obj2pcd`` installable with

.. code-block:: bash

    $ sudo apt install pcl-tools

Here the step by step procedure:

- Create the stl file to 3D print the object via `FreeCAD <https://www.freecad.org/>`_ or similar
- Import the stl file via `Blender <https://www.blender.org/>`_

.. image:: /images/html/importSTL.png
   :alt: Import STL Blender menu


- Edit so the metrics matches the Realsense Camera metrics: Units are in meters AND the center of the object is in the origin of blender and parallel to the axes where applicable. In short, perform scaling, rotating and translating operations so that dimension matches the realsense camera and the rototranslation from blender origin matches the desired outcome. For example, looking at the following image, the imported STL has been scaled down so the side of the cube is 5CM (0.05 meters), and translated down the Z axis of 0.025 centimeters, so the center of the cube is at 0,0,0. No rotation was needed as the cube was already parallel to the absolute reference system.

.. image:: /images/html/editObject.png
   :alt: Transform object by scaling, rotating and translating with Blender

- Export the object in WaveFront format (.obj) as shown in picture

.. image:: /images/html/exportToObj.png
   :alt: Blender menu to export selected object to WaveFront format


- Convert the .obj file to pcd file with pcl_obj2pcd   

Note: Important consideration: The RVC Pose Detector will align this object PCD file to the input cloud from realsense. This means calculating how much every points of the object pcd are translated and rotated on top of the realsense poincloud from the original file location. To have a consistent meaning, the object baricenter should be in the origin to simulate the center of the optical camera (where all the optical and depth information are translated to). in this way, the algorithm will determine how far and how rotated is the object from the camera optical lense. if the object is not centered in 0,0,0, this calculation would be wrong. See following picture:


.. image:: /images/html/CenteredObject.png
   :alt: Vertices of a 0,0,0 centered object


PCD file creation from Blender Modeler
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We used the Open Source 3D modeler `Blender <https://www.blender.org/>`_

We create the object and then assured there was enough vertices by subdividing the mesh (ctrl R in edit mode), see: `Method 2 <https://themotiontree.com/how-to-subdivide-in-blender/>`_

Then export the mesh in obj format and converting it with pcl_obj2pcd as exposed above.

Verify that the PCD file has enough points using the pcl_viewer tool which comes togheter with pcl_obj2pcd:

.. code-block:: bash

  $ pcl_viewer <pcdFilename.pcd>

As show in following image  


.. image:: /images/html/pcl_viewer.png
   :alt: PCD visualizer

rvc_use_case_binaries package creation
--------------------------------------

- Create a `Ros2 package <https://docs.ros.org/en/foxy/Tutorials/Beginner-Client-Libraries/Creating-Your-First-ROS2-Package.html>`_ named rvc_use_case_binaries

and adapt the files


.. code-block:: xml

    <?xml version="1.0"?>
    <?xml-model href="http://download.ros.org/schema/package_format3.xsd" schematypens="http://www.w3.org/2001/XMLSchema"?>
    <package format="3">
    <name>rvc_use_case_binaries</name>
    <version>2.0.0</version>
    <description>Package containing sample PCD objects and AI models</description>
    <maintainer email="robotics@intel.com">Intel Robotics Team</maintainer>
    <license>Propertary</license>

    <buildtool_depend>ament_cmake</buildtool_depend>

    <test_depend>ament_lint_auto</test_depend>
    <test_depend>ament_lint_common</test_depend>

    <export>
        <build_type>ament_cmake</build_type>
    </export>
    </package>


.. code-block:: cmake

    cmake_minimum_required(VERSION 3.8)
    project(rvc_use_case_binaries)

    find_package(ament_cmake REQUIRED)

    install(FILES
      ai_models/yolo_nano.xml
      ai_models/yolo_nano.bin
      DESTINATION
      share/${PROJECT_NAME}/ai_models
      )

    install(FILES
      pcd_objects/obj1.pcd
      pcd_objects/obj2.pcd
      [...]
      DESTINATION
      share/${PROJECT_NAME}/pcd_objects
      )

    ament_package()

to match your object ``.pcd`` files

- Create ai_models and pcd_objects directories inside this package

- Add yolo models in ai_models and pcd files in pcd_objects

.. note:: The models are converted in <modelname>_openvino_model in the yolov5 dir

- Edit parameters.yaml of object_detection and pose_detection to match the names of these files

Container execution:
====================


.. code-block:: bash

    ros2 launch rvc_vision_main vision.composition.launch.py <namespace:=ipc>
