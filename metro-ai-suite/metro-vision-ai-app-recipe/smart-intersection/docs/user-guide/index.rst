Smart Intersection
========================================

Smart Intersection Sample Application uses edge AI to improve traffic flow. It combines feeds from multiple cameras to track vehicles across angles, analyze speed and direction, and understand interactions in real space. The system can run on existing cameras and deliver real-time, coordinated insights for smarter traffic monitoring.

**Example Use Cases**
- **Pedestrian Safety**: Enhance safety for people crossing the street. The system tracks pedestrians at crosswalks. It alerts when people walk outside safe crossing areas.
- **Traffic Flow Monitoring**: Count vehicles and measure dwell time in each lane. The system detects when vehicles stay too long in lanes. This identifies stalled cars, accidents, and traffic jams.

**Key Benefits**

The key benefits are as follows:

- **Multi-camera multi-object tracking**: Enables tracking of objects across multiple camera views.
- **Scene based analytics**: Regions of interest that span multiple views can be easily defined on the map rather than independently on each camera view. This greatly simplifies business logic, enables more flexibility in defining regions, and allows various types of sensors to be used to track vehicles and people such as lidar and radar in addition to cameras.
- **Improved Urban Management**: Object tracks and analytics are available near-real-time on the MQTT broker to enable actionable insights for traffic monitoring and safety applications.
- **Reduced TCO**: Works with existing cameras, simplifies business logic development, and future-proofs the solution by enabling additional sensors and cameras as needed without changing the business logic.

This guide is designed to help developers understand the architecture, setup, and customization of the sample application.


.. toctree::

   Overview
   how-it-works
   system-requirements
   get-started
   how-to-deploy-helm
   support
