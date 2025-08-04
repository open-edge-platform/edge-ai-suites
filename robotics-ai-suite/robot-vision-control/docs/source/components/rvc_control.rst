.. _rvc_control:

Control
***********


.. _High Level Design:

.. image:: /images/html/RVCControl.png
   :alt: High Level Design

The above :ref:`High Level Design <High Level Design>` diagram shows in communication between 
the motion controller components.
This interaction is left to be implemented in a |ros| node. Our use cases utilize a state machine. The |ros| node
will initialize the |ros| framework, initialize the intended plugins and delegate the use case handling to the state machine:



1. The state machine will instantiate a reference to a plugin of interface "GraspInterface" and one
of interface "MotionController" according to the specified configuration as in :ref:`Example Configuration<example_configuration>`


2. The Grasp Plugin will subscribe to the :ref:`RVC API messages<rvc_api_messages>` RotatedBBList and compute the 
target pose for the robot.

3. According to the state of the state machine, this is used
to ask the instance of the :ref:`MotionController plugin<motion_controller_plugin>` to go the target and/or achieve different
tasks.



.. toctree::
   :maxdepth: 1
   :hidden:

   rvc_control/parameters
   rvc_control/motion_controller_plugin
   rvc_control/grasp_plugin
