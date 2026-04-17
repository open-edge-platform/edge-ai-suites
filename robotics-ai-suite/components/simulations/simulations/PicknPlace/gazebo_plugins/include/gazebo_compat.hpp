// SPDX-License-Identifier: Apache-2.0
/*
 * Copyright (C) 2017 Open Source Robotics Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
*/

// Gazebo Compatibility Layer for Fortress (6.x) and Harmonic (8.x+)

#ifndef GAZEBO_COMPAT_HPP_
#define GAZEBO_COMPAT_HPP_

// Compatibility layer for different Gazebo versions
#if defined(GAZEBO_MAJOR_VERSION) && GAZEBO_MAJOR_VERSION >= 8
  // Gazebo Harmonic (8.x+) - use gz headers
  #include <gz/sim/Model.hh>
  #include <gz/sim/Link.hh>
  #include <gz/sim/World.hh>
  #include <gz/sim/Entity.hh>
  #include <gz/sim/Util.hh>
  #include <gz/sim/Sensor.hh>
  #include <gz/sim/System.hh>
  #include <gz/plugin/Register.hh>
  #include <gz/sim/EntityComponentManager.hh>
  #include <gz/sim/EventManager.hh>
  #include <gz/sim/components.hh>
  #include <gz/transport/Node.hh>
  #include <gz/msgs/contacts.pb.h>
  #include <gz/msgs/entity.pb.h>
  #include <gz/msgs/pose.pb.h>
  #include <gz/msgs/twist.pb.h>
  #include <gz/msgs/vector3d.pb.h>
  #include <gz/math/Pose3.hh>
  #include <gz/math/Vector3.hh>
  #include <gz/math/Quaternion.hh>
  #include <gz/common/Console.hh>
  
  // Namespace aliases for Harmonic
  namespace gazebo = gz::sim;
  namespace gz_transport = gz::transport;
  namespace gz_msgs = gz::msgs;
  namespace gz_math = gz::math;
  
  // Plugin registration macro
  #define GAZEBO_ADD_PLUGIN(classname, ...) \
    GZ_ADD_PLUGIN(classname, __VA_ARGS__)
    
#else
  // Gazebo Fortress (6.x) - use gz headers from system paths
  #include <gz/sim/Model.hh>
  #include <gz/sim/Link.hh>
  #include <gz/sim/World.hh>
  #include <gz/sim/Entity.hh>
  #include <gz/sim/Util.hh>
  #include <gz/sim/Sensor.hh>
  #include <gz/sim/System.hh>
  #include <gz/plugin/Register.hh>
  #include <gz/sim/EntityComponentManager.hh>
  #include <gz/sim/EventManager.hh>
  #include <gz/sim/components.hh>
  #include <gz/transport/Node.hh>
  #include <gz/msgs/contacts.pb.h>
  #include <gz/msgs/entity.pb.h>
  #include <gz/msgs/pose.pb.h>
  #include <gz/msgs/twist.pb.h>
  #include <gz/msgs/vector3d.pb.h>
  #include <gz/math/Pose3.hh>
  #include <gz/math/Vector3.hh>
  #include <gz/math/Quaternion.hh>
  #include <gz/common/Console.hh>
  
  // Namespace aliases for Fortress (same as Harmonic)
  namespace gazebo = gz::sim;
  namespace gz_transport = gz::transport;
  namespace gz_msgs = gz::msgs;
  namespace gz_math = gz::math;
  
  // Plugin registration macro - try GZ first, fallback to IGNITION
  #ifdef GZ_ADD_PLUGIN
    #define GAZEBO_ADD_PLUGIN(classname, ...) \
      GZ_ADD_PLUGIN(classname, __VA_ARGS__)
  #else
    #define GAZEBO_ADD_PLUGIN(classname, ...) \
      IGNITION_ADD_PLUGIN(classname, __VA_ARGS__)
  #endif
    
#endif

#endif // GAZEBO_COMPAT_HPP_
