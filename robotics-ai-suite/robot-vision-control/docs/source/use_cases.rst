:next_page: None
:prev_page: None

.. _use_cases:

Exemplary Use Cases
##############################


Two use cases are delivered using the RVC framework trying to cover as many options as possible


- :ref:`dynamic_use_case`: Vision will track the position of 4 different object classes and the robot will catch one while it is still moving
- :ref:`static_use_case`: Vision will detect the pose of a still object and the robot will align the gripper to pick it up an oriented way.

.. note:: 

    We strongly suggest to set the real robot in this home position, and move it there before starting any of the provided use cases:

.. image:: /images/html/sethomeposition.png
   :alt: setting home position

.. image:: /images/html/homeposition.png
   :alt: home position


.. toctree::
   :maxdepth: 1
      
   use_cases/dynamic_use_case
   use_cases/static_use_case
