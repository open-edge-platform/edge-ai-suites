Autonomous Mobile Robot
************************

The Autonomous Mobile Robot provides software packages and pre-validated hardware modules for sensor data ingestion, classification, environment modeling, action planning, action control. Built on the (ROS 2 Humble) robot operating system, it also features reference algorithms and working examples.

Beyond autonomous mobility, this package demonstrates map building and Simultaneous Localization And Mapping (SLAM) loop closure functionality. It utilizes an open source version of visual SLAM with input from an Intel® RealSense™ camera. Optionally, the package allows you to run Light Detection and Ranging (LiDAR) based SLAM and compare those results with visual SLAM results on accuracy and performance indicators. Additionally, it detects and highlights the objects on the map. Depending on the platform that is used, workloads are executed on an integrated GPU or on Intel® CPU.

The Autonomous Mobile Robot addresses industrial, manufacturing, consumer market, and smart cities use cases, facilitating data collection, storage, and analytics across various nodes on the factory floor.
Develop, build, and deploy end-to-end mobile robot applications with this purpose-built, open, and modular software development kit that includes libraries, middleware, and sample applications based on the open source ROS 2 Humble robot operating system.

Click each icon to learn more.

.. grid:: 2

    .. grid-item-card:: Get Started with Autonomous Mobile Robot
        :link: gsg_robot/index
        :link-type: doc
        :link-alt: clickable cards

        Install a Robot Kit.

    .. grid-item-card:: How it works
        :link: dev_guide/index_howitworks
        :link-type: doc
        :link-alt: clickable cards

        Describes how the software works

    .. grid-item-card:: Tutorials
        :link: dev_guide/index_tutorials
        :link-type: doc
        :link-alt: clickable cards

        Provides a learning path for developers to use and configure Autonomous Mobile Robot

    .. grid-item-card:: System Integrators
        :link: dev_guide/index_systemintegrator
        :link-type: doc
        :link-alt: clickable cards

        Information specifically for System Integrators.


.. toctree::
   :maxdepth: 1
   :hidden:

   gsg_robot/index
   shared/requirements_robot
   dev_guide/index_howitworks
   dev_guide/index_tutorials
   dev_guide/index_systemintegrator
   dev_guide/index_gmslguide
   Release Notes <release-notes>