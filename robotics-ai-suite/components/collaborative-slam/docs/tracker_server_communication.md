### Background

This document is used to introduce the communication mechanism between tracker and server nodes. The original implementation is based on the TCP socket and now we move it to [ROS Service](https://docs.ros.org/en/foxy/Tutorials/Services/Understanding-ROS2-Services.html). Once a service client and a service server have established a connection, the communication between these two sides is safe and reliable, just like the TCP socket does. In addition, the requests and responses of a ROS service can not be captured and that's why we decide not to use [ROS Topic](https://docs.ros.org/en/foxy/Tutorials/Topics/Understanding-ROS2-Topics.html).

---

### Model

Each connection between a tracker node and a server node includes a pair of ROS services. One is the public service for the tracker node to send all kinds of requests to the server node; another is the private service for the server node to send the processing result back to the tracker node. Why we decide to use two services is that, both of tracker and server nodes need to actively trigger a transmission in our current design, so we don't design the server node only as a service server and can only send back the responses after the return of service callback function. 

**Public Service**
All the public services in different tracker nodes have a common name `tracker2server`. In this public service, the tracker node will work as a service client when sending requests to the server node. Meanwhile, the server node will work as a service server to receive these requests and only do the enqueue operations in its callback funtion. All the related complex computing workloads are done by other threads of server node. And once the threads finish the computing, they will actively trigger a transmission to send the results back to the tracker node through private service. At the startup of a tracker node, it will first start a thread to do `wait_for_service` and continuously connect to the public service server of server node.

**Private Service**
The private services in different tracker nodes have different names with the format `server2tracker_$(ID)`. The parameter `ID` is the tracker ID which can be configured in the tracker launch file with a default value 0. In this private service, the server node will work as a service client when sending processing results back to the tracker node. Meanwhile, the tracker node will work as a service server to receive these results and take corresponding actions. On startup, once the public service is established (`wait_for_service` is done) on tracker node, it will send a connecting request to server node via public service. When receiving this connecting request, the server node will start a new thread and in which to create a private service client to continuously connect to the private service server of tracker node by doing `wait_for_service`. After the wait is done, the server node will then send the connecting request back to the tracker node via this private service which let the tracker node can confirm the connection between tracker and server node is finally established.

---

### Message Format

The message format we use for the communication between service client and service server is like below. The service client will send a [Map.msg](../msgs/msg/Map.msg) request and the service server will acknowledge it with a bool (true/false) response.

```
Map req_map
---
bool resp_status
```
