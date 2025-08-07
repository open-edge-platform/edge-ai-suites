
.. _example_configuration:

Example Configuration
~~~~~~~~~~~~~~~~~~~~~

The main node plugin configuration can be provided by yaml file, as per
following examples:


Plugins
^^^^^^^^
.. _interface_config:

.. code-block:: yaml

   /**:
       ros__parameters:
           motion_controller: "RVCMotionController::Moveit2ServoMotionController"
           grasp_plugin: "RVCControl::NonOrientedGrasp"

To use Dobby planner plugin:

.. code-block:: yaml

   /**:
       ros__parameters:
           motion_controller: "RVCMotionController::DobbyMotionController"
