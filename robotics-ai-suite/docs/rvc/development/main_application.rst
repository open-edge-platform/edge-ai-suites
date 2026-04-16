
.. _main_application:

Main Application
###################

The specific use case application, also known as the decisional program, must adhere to certain rules to integrate with the RVC Framework.

.. _main_application_development:

Main Application Development
=============================

This RVC Component is centered around the motion controller aspect of the RVC Framework. The workflow, in a high-level detail, is as follows: 

- An API message, output rvc_messages, is received. 
- The active grasp plugin computes the pre-grasp and grasp pose for the gripper, also known as the Tool Center Point (TCP). 
- A State machine or an equivalent programmatic approach is used to decide actions and, if applicable, move the robot to the pre-grasp and then grasp positions, activating the gripper via the selected RVCMotionController::RVCMotionControllerInterface based plugin.

State Machine Snippet
----------------------
The ROS2 node that implements the decisional process needs to load two plugins according to ROS2 parameters. These parameters can be loaded via a launcher, command line, or yaml file.

Example in C++
--------------

.. code-block:: c++

   #include "rvc_dynamic_motion_controller_use_case/state_machine.hpp"

   #include "rvc_motion_controller_interface/rvc_motion_controller_interface.hpp"
   #include "rvc_grasp_interface/rvc_grasp_interface.hpp"
   #include <pluginlib/class_loader.hpp>

   int main(int argc, char ** argv)
   {
       rclcpp::init(argc, argv);

       auto stateMachine = std::make_shared<StateMachine>();

       stateMachine->declare_parameter<std::string>("motion_controller",
           "RVCMotionController::Moveit2ServoMotionController");
       stateMachine->declare_parameter<std::string>("grasp_plugin", "RVCControl::NonOrientedGrasp");
       std::string motionControllerName = stateMachine->get_parameter("motion_controller").as_string();
       std::string graspPluginName = stateMachine->get_parameter("grasp_plugin").as_string();

       pluginlib::ClassLoader<RVCMotionController::RVCMotionControllerInterface> motionControllerLoader(
           "rvc_motion_controller_interface", "RVCMotionController::RVCMotionControllerInterface");
       std::shared_ptr<RVCMotionController::RVCMotionControllerInterface> motionController;
       pluginlib::ClassLoader<RVCControl::RVCGraspInterface> graspLoader("rvc_grasp_interface",
           "RVCControl::RVCGraspInterface");
       std::shared_ptr<RVCControl::RVCGraspInterface> graspPlugin;

       motionController = motionControllerLoader.createSharedInstance(motionControllerName);

       if (!motionController->init(stateMachine))
       {
           return 1;
       }

       graspPlugin = graspLoader.createSharedInstance(graspPluginName);

       if (!graspPlugin->init(stateMachine))
       {
           return 1;
       }

       bool ret = stateMachine->init(motionController.get(), graspPlugin.get());

       if (ret)
       {
           rclcpp::spin(stateMachine);
       }

       rclcpp::shutdown();

       return 0;
   }


This application will create an instance of a "StateMachine" class, inheriting from rclcpp::Node from 
ROS2 framework [TODO: link], and passing the smart pointers of the grasp and motion controller Interface  instances. 

For Example

.. code-block:: c++

    #include "rclcpp/rclcpp.hpp"

    class StateMachine : public rclcpp::Node
    {
    private:

        /// @brief internal run function to be called on a fixed timer to handle the state machine
        void run(void);
    public:
        /// @brief Constructor, parameterless
        StateMachine();
        bool init(RVCMotionControllerInterface *motionController, RVCControl::RVCGraspInterface *graspPlugin);
    };


where init will store the interface references and start the state machine internal processing.

Two more practical example are redistributed with rvc_dynamic_motion_controller_use_case and
rvc_static_motion_controller_use_case state_machine.cpp and .hpp
