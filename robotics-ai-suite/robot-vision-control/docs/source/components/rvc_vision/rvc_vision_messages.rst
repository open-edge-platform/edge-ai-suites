
.. _rvc_vision_messages:

RVC Vision Messages
====================

Two |ROS| custom messages have been created for the dynamic use case Vision container internal
communication: ``rvc_vision_messages``

rvc_vision_messages contains following messages:

RotatedBB
~~~~~~~~~

Field description:

- Bounding box center coordinates: cx,cy
- Bounding box dimensions: width, height
- Bounding box angle: angle
- Unique id of the object class: object_id
- AI detection confidence level: confidence_level

RotatedBBList
~~~~~~~~~~~~~

This message is a container of RotatedBB message

- Array of RotatedBB messages

