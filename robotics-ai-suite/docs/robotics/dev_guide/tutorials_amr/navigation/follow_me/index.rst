Follow-me Algorithm
=====================

The Follow-me algorithm is a |p_amr| application for following a target person without any manual or external control dependency. The complete pipeline is described here.
A comprehensive diagram of the application is showed in the figure below. The |deb_packs| are outlined with *blue* rectangles in the figure.

**Applications (processing inputs)**


This multimodal solution can control robot motion by any combination of the following three factors:

- **Target person's proximity/location:** We use an |intel|-patented point cloud-based object detection and localization algorithm, called ADBSCAN, for this purpose. 
  It takes point cloud data as inputs from a 2D LIDAR or RGB-D camera and outputs the presence and location of the target (to be followed). 
  `ros-humble-adbscan-ros2-follow-me` package launches this node. This module is present in all versions of the Follow-me algorithm.
- **Hand gesture of the target:** An open-source deep learning model, developed by Google’s Mediapipe framework, is used for the target person’s hand gesture recognition from RGB image.
  See `Mediapipe Hands <https://mediapipe.readthedocs.io/en/latest/solutions/hands.html>`_ for more details of the model. `ros-humble-gesture-recognition-pkg` subscribes to the RGB image and publishes |ros| topic with gesture category `msg`.
- **Voice command:** A pre-trained neural network, called Quartznet, is used for automatic speech recognition and convert the target person’s voice commands into robot motion control commands. 
  The pre-trained `Quartznet <https://docs.openvino.ai/2023.3/omz_models_model_quartznet_15x5_en.html>`_ parameters are obtained from |openvino| model zoo. `ros-humble-speech-recognition-pkg` launches this node and publishes |ros| topic with voice-based robot control commands.
  

------------------------------

**Applications (processing outputs)**


The outputs of all or a combination of the above modules are used to determine robot's velocity and publish ``twist`` `msg`, which can be subsequently used by a real robot or a simulated robot in `Gazebo`.
The demos on real robots and simulation environments are referred to as `Tutorials` and `Simulation Demos` respectively. You can navigate to each of these categories using the following links:

.. toctree::
   :maxdepth: 2

   Simulation_demos/index
   Tutorials/index

The demo with audio control contains an additional node (`ros-humble-text-to-speech-pkg`) containing a text to speech synthesis module to enable audio narration 
of the robot's activity during the course of its movement. This module uses pre-trained text-to-speech synthesis model, called `Forward-Tacotron <https://docs.openvino.ai/2023.3/omz_models_model_forward_tacotron.html>`_ from |openvino| model zoo.


   .. image:: ../../../../images/follow-me_complete_2024.png


.. note::

  Please display a disclaimer/signage/visible notice to the surrounding people stating the use of voice-activated/gesture recognition technology while the follow-me application with audio and/or gesture is in use.

  Also please keep in mind that the accuracy of the speech recognition model may vary depending on the user demography. We recommend that any application using `follow-me with audio control` to undergo bias testing (dependence on the voice of the user demography) appropriate to the context of use.


