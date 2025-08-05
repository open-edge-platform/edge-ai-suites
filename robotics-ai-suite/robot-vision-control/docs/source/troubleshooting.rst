:next_page: None
:prev_page: None

Troubleshootings
##############################

#. Inference on GPU does not work?

    .. code-block:: bash
    
       $ sudo -E apt install clinfo
       $ clinfo

    Verify that the GPU is part of supported platforms:

    ::

       Number of platforms                             1
       Platform Name                                   Intel(R) OpenCL HD Graphics
       Platform Vendor                                 Intel(R) Corporation
       Platform Version                                OpenCL 3.0
       Platform Profile                                FULL_PROFILE

#. Robot does not move?

    First start the motion controller, then press play on the pendant.

#. Robot arm does not go accurately pick up the object?

    Check :ref:`Camera pose calibration<camera_pose_calibration>`

