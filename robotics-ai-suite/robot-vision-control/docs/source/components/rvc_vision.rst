

.. _vision_abstract:

Vision
==========

The RVC Vision can be divided in two use case based sets of components:

- :ref:`dynamic_vision`
- :ref:`2.5d_vision`

The former is actively tracking a set of object based of a Deep Neural Network (DNN) in 2D world-space
and then feeding the results to a second stage sub-component deriving the 3D space 6DoF pose using
a depth based stream from the camera algorithm based on Pointcloud object matching

The latter is using Computer vision 2.5D space recognition based solely on RGB stream of a camera
to derive a non real time pose of an object standing still a fixed distance surface.


.. toctree::
   :maxdepth: 1
   :hidden:
   
   rvc_vision/dynamic_vision
   rvc_vision/2.5d_vision/2.5d_vision
   rvc_vision/rvc_vision_messages

