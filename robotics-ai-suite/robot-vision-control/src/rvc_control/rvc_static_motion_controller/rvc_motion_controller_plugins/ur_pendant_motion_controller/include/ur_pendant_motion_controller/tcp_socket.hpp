/*
 * SPDX-License-Identifier: Apache-2.0
 * SPDX-FileCopyrightText: (C) 2019 FZI Forschungszentrum Informatik Copyright 2015, 2016 Thomas Timm Andersen (original version) 2017, 2018 Simon Rasmussen (refactor)
 * Copyright 2019, FZI Forschungszentrum Informatik (refactor)
 *
 * Copyright 2017, 2018 Simon Rasmussen (refactor)
 *
 * Copyright 2015, 2016 Thomas Timm Andersen (original version)
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
 */


#pragma once

#include <cstdio>
#include <memory>
#include <sstream>
#include <fstream>

#include <arpa/inet.h>
#include <endian.h>
#include <netinet/tcp.h>
#include <cstring>
#include <thread>

#include <netdb.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <atomic>
#include <mutex>
#include <string>
#include <memory>

#include <unistd.h>
#include <functional>

#include <rclcpp/rclcpp.hpp>
#include <fcntl.h>

/// @brief main of the application, spawns a state machine node and a goalcontroller and spi ros2
/// @param argc argument count
/// @param argv argument vector
/// @return 0 on success, 1 on failure

enum class SocketState
{
  Invalid,       ///< Socket is initialized or setup failed
  Connected,     ///< Socket is connected and ready to use
  Disconnected,  ///< Socket is disconnected and cannot be used
  Closed         ///< Connection to socket got closed
};

/*!
 * \brief Class for TCP socket abstraction
 */
class TCPSocket
{
private:
  std::atomic<int> socket_fd_;
  std::atomic<SocketState> state_;
  std::chrono::seconds reconnection_time_;

protected:
  virtual void setOptions(int socket_fd);

  std::unique_ptr<timeval> recv_timeout_;

public:
  bool setup(std::string& host, int port);
  TCPSocket();
  virtual ~TCPSocket();
  std::string getIP() const;
  bool read(char* character);
  bool read(uint8_t* buf, const size_t buf_len, size_t& read);
  bool write(const uint8_t* buf, const size_t buf_len, size_t& written);
  void close();
};



