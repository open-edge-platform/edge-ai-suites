The ROS packages in this repository were created to provide an alternative
Inverse Kinematics solver to the popular inverse Jacobian methods in KDL.
Specifically, KDL's convergence algorithms are based on Newton's method, which
does not work well in the presence of joint limits --- common for many robotic
platforms.  TRAC-IK concurrently runs two IK implementations.  One is a simple
extension to KDL's Newton-based convergence algorithm that detects and
mitigates local minima due to joint limits by random jumps.  The second is an
SQP (Sequential Quadratic Programming) nonlinear optimization approach which
uses quasi-Newton methods that better handle joint limits.  By default, the IK
search returns immediately when either of these algorithms converges to an
answer.  Secondary constraints of distance and manipulability are also provided 
in order to receive back the "best" IK solution.  
**Note:** TRAC-IK is built on top of the KDL library, which is not thread safe (there's some internals that I think use _static_ variables).  Thus, you should not use multiple instances of TRAC-IK in the same process.

###This repo contains 5 ROS packages:###

- trac\_ik is a metapackage with build and complete [Changelog](https://bitbucket.org/traclabs/trac_ik/src/HEAD/trac_ik/CHANGELOG.rst) info.

- trac\_ik\_examples contains examples on how to use the standalone TRAC-IK library.

- [trac\_ik\_lib](https://bitbucket.org/traclabs/trac_ik/src/HEAD/trac_ik_lib), the TRAC-IK kinematics code,
builds a .so library that can be used as a drop in replacement for KDL's IK
functions for KDL chains. Details for use are in trac\_ik\_lib/README.md.

- [trac\_ik\_kinematics\_plugin](https://bitbucket.org/traclabs/trac_ik/src/HEAD/trac_ik_kinematics_plugin) builds a [MoveIt! plugin](http://moveit.ros.org/documentation/concepts/#kinematics) that can
replace the default KDL plugin for MoveIt! with TRAC-IK for use in planning.
Details for use are in trac\_ik\_kinematics\_plugin/README.md. (Note prior to v1.1.2, the plugin was not thread safe.)

- [trac\_ik\_python](https://bitbucket.org/traclabs/trac_ik/src/HEAD/trac_ik_python), SWIG based python wrapper to use TRAC-IK. Details for use are in trac\_ik\_python/README.md.


###As of v1.4.5, this package is part of the ROS Kinetic binaries: `sudo apt-get install ros-kinetic-trac-ik` (or indigo or jade).  Starting with v1.4.8, this has been released for ROS Lunar as well. Melodic packages have been released with 1.5.0.


###A detailed writeup on TRAC-IK can be found here:###

[Humanoids-2015](https://www.researchgate.net/publication/282852814_TRAC-IK_An_Open-Source_Library_for_Improved_Solving_of_Generic_Inverse_Kinematics) (reported results are from v1.0.0 of TRAC-IK, see below for newer results).

###Some sample results are below: 

_Orocos' **KDL**_ (inverse Jacobian w/ joint limits), _**KDL-RR**_ (our fixes to KDL joint limit handling), and _**TRAC-IK**_ (our concurrent inverse Jacobian and non-linear optimization solver; Speed mode) are compared below.

IK success and average speed as of TRAC-IK tag v1.5.1.  All results are from 10,000 randomly generated, reachable joint configurations.  Full 3D pose IK was requested at 1e-5 Cartesian error for x,y,z,roll,pitch,yaw with a maximum solve time of 5 ms.  All IK queries are seeded from the chain's "nominal" pose midway between joint limits.

**Note on success**: Neither KDL nor TRAC-IK uses any mesh information to determine if _valid_ IK solutions result in self-collisions.  IK solutions deal with link distances and joint ranges, and remain agnostic about self-collisions due to volumes.  Expected future enhancements to TRAC-IK that search for multiple solutions may also include the ability to throw out solutions that result in self collisions (provided the URDF has valid geometry information); however, this is currently not the behaviour of any generic IK solver examined to date.

**Note on timings**: The timings provided include both successful and unsuccessful runs.  When an IK solution is not found, the numerical IK solver implementations will run for the full timeout requested, searching for an answer; thus for robot chains where KDL fails much of the time (e.g., Jaco-2), the KDL times are skewed towards the user requested timeout value (here 5 ms).  

Chain | DOFs | Orocos' _KDL_ solve rate | Orocos' _KDL_ Avg Time | _KDL-RR_ solve rate | _KDL-RR_ Avg Time | _TRAC-IK_ solve rate | _TRAC-IK_ Avg Time
- | - | - | - | - | - | - | -
ABB IRB120 | 6 | **39.41%** | 3.08ms | **98.51%** | 0.33ms | **99.96%** | 0.24ms
ABB Yumi 'single arm' | 7 | **77.35%** | 1.43ms | **91.31%** | 0.87ms | **99.70%** | 0.42ms
Atlas 2013 arm | 6 | **75.54%** | 1.32ms | **97.24%** | 0.34ms | **99.99%** | 0.20ms
Atlas 2015 arm | 7 | **76.22%** | 1.44ms | **94.12%** | 0.71ms | **99.80%** | 0.32ms
Baxter arm | 7 | **61.43%** | 2.15ms | **90.78%** | 0.91ms | **99.83%** | 0.37ms
Denso VS-068 | 6 | **27.95%** | 3.67ms | **98.32%** | 0.35ms | **99.96%** | 0.26ms
Fanuc M-430iA/2F | 5 | **21.08%** | 3.98ms | **88.69%** | 0.84ms | **99.93%** | 0.36ms
Fetch arm | 7 | **93.28%** | 0.65ms | **94.72%** | 0.63ms | **99.98%** | 0.24ms
Franka Emika Panda | 7 | **62.02%** | 2.11ms | **93.21%** | 0.79ms | **99.88%** | 0.37ms
Jaco2 | 6 | **26.25%** | 3.77ms | **97.85%** | 0.47ms | **99.92%** | 0.35ms
KUKA LBR iiwa 14 R820 | 7 | **38.09%** | 3.31ms | **95.15%** | 0.64ms | **99.92%** | 0.28ms
KUKA LWR 4+ | 7 | **68.22%** | 1.82ms | **96.26%** | 0.53ms | **99.98%** | 0.23ms
Motoman CSDA10F 'torso/1-arm' | 8 | **53.58%** | 2.73ms | **96.08%** | 0.60ms | **99.96%** | 0.32ms
Motoman MH180 | 6 | **68.46%** | 1.65ms | **99.39%** | 0.22ms | **99.99%** | 0.18ms
NASA Robonaut2 arm | 7 | **86.89%** | 0.96ms | **95.23%** | 0.64ms | **99.85%** | 0.30ms
NASA Robonaut2 'grasping leg' | 7 | **61.70%** | 2.21ms | **88.77%** | 1.00ms | **99.91%** | 0.40ms
NASA Robonaut2 'leg' + waist + arm | 15 | **98.42%** | 0.67ms | **98.58%** | 0.66ms | **99.83%** | 0.57ms
NASA Robosimian arm | 7 | **62.10%** | 2.33ms | **99.88%** | 0.28ms | **99.97%** | 0.30ms
NASA Valkyrie arm | 7 | **45.78%** | 2.95ms | **92.34%** | 1.11ms | **99.90%** | 0.37ms
PR2 arm | 7 | **84.70%** | 1.26ms | **88.82%** | 1.15ms | **99.96%** | 0.31ms
Schunk LWA4D | 7 | **68.57%** | 1.79ms | **97.26%** | 0.43ms | **100.00%** | 0.23ms
TRACLabs modular arm | 7 | **79.59%** | 1.28ms | **96.11%** | 0.54ms | **99.99%** | 0.27ms
Universal UR3 | 6 | **17.11%** | 4.18ms | **89.08%** | 0.77ms | **98.60%** | 0.45ms
UR5 | 6 | **16.52%** | 4.21ms | **88.58%** | 0.74ms | **99.17%** | 0.37ms
UR10 | 6 | **14.90%** | 4.29ms | **88.63%** | 0.74ms | **99.33%** | 0.36ms

Feel free to [email TRACLabs Robotics](mailto:robotics@traclabs.com) if you have any issues.
