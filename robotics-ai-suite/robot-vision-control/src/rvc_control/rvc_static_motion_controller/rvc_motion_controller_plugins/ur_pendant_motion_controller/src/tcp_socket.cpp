/*
 * SPDX-License-Identifier: Apache-2.0   
 * SPDX-FileCopyrightText: (C) 2019 FZI Forschungszentrum Informatik (refactor) 2017, 2018 Jarek Potiuk (low bandwidth trajectory follower) 2017, 2018 Simon Rasmussen (refactor) 2015, 2016 Thomas Timm Andersen (original version)
 * Copyright 2019, FZI Forschungszentrum Informatik (refactor)
 *
 * Copyright 2017, 2018 Jarek Potiuk (low bandwidth trajectory follower)
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

#include "ur_pendant_motion_controller/tcp_socket.hpp"

TCPSocket::TCPSocket() : socket_fd_(-1), state_(SocketState::Invalid), reconnection_time_(std::chrono::seconds(10))
{
}
TCPSocket::~TCPSocket()
{
  close();
}

void TCPSocket::setOptions(int socket_fd)
{
  int flag = 1;
  setsockopt(socket_fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(int));
  setsockopt(socket_fd, IPPROTO_TCP, TCP_QUICKACK, &flag, sizeof(int));

  if (recv_timeout_ != nullptr)
  {
    setsockopt(socket_fd, SOL_SOCKET, SO_RCVTIMEO, recv_timeout_.get(), sizeof(timeval));
  }
}

bool TCPSocket::setup(std::string& host, int port)
{
  if (state_ == SocketState::Connected)
    return false;

  RCLCPP_INFO(rclcpp::get_logger("PP"),"Setting up connection: %s:%d", host.c_str(), port);

  // gethostbyname() is deprecated so use getadderinfo() as described in:
  // https://beej.us/guide/bgnet/html/#getaddrinfoprepare-to-launch

  std::string service = std::to_string(port);
  struct addrinfo hints;
  std::memset(&hints, 0, sizeof(hints));

  hints.ai_family = AF_UNSPEC;
  hints.ai_socktype = SOCK_STREAM;
  hints.ai_flags = AI_PASSIVE;

  bool connected = false;

  struct sockaddr_in serv_addr;
  int status;
  if ((socket_fd_ = socket(AF_INET, SOCK_STREAM, 0)) < 0) 
  {
        printf("\n Socket creation error \n");
        return -1;
  }
 
  serv_addr.sin_family = AF_INET;
  serv_addr.sin_port = htons(port);
 
    // Convert IPv4 and IPv6 addresses from text to binary
    // form
    if (inet_pton(AF_INET, host.c_str(), &serv_addr.sin_addr)
        <= 0) {
       std::cout << "\nInvalid address/ Address not supported \n";
        return false;
    }
 
    if ((status
         = connect(socket_fd_, (struct sockaddr*)&serv_addr,
                   sizeof(serv_addr))) < 0) {
        std::cout << "\nConnection Failed \n";
        return false;
    }
    connected = true;

  setOptions(socket_fd_);
  state_ = SocketState::Connected;
  RCLCPP_INFO(rclcpp::get_logger("PP"),"Connection established for %s:%d", host.c_str(), port);
  return connected;
}

void TCPSocket::close()
{
  if (socket_fd_ >= 0)
  {
    state_ = SocketState::Closed;
    ::close(socket_fd_);
    socket_fd_ = -1;
  }
}

std::string TCPSocket::getIP() const
{
  sockaddr_in name;
  socklen_t len = sizeof(name);
  int res = ::getsockname(socket_fd_, (sockaddr*)&name, &len);

  if (res < 0)
  {
    RCLCPP_ERROR(rclcpp::get_logger("PP"),"Could not get local IP");
    return std::string();
  }

  char buf[128];
  inet_ntop(AF_INET, &name.sin_addr, buf, sizeof(buf));
  return std::string(buf);
}

bool TCPSocket::read(char* character)
{
  size_t read_chars;
  // It's inefficient, but in our case we read very small messages
  // and the overhead connected with reading character by character is
  // negligible - adding buffering would complicate the code needlessly.
  return read((uint8_t*)character, 1, read_chars);
}

bool TCPSocket::read(uint8_t* buf, const size_t buf_len, size_t& read)
{
  read = 0;

  if (state_ != SocketState::Connected)
    return false;

  ssize_t res = ::recv(socket_fd_, buf, buf_len, 0);

  if (res == 0)
  {
    state_ = SocketState::Disconnected;
    return false;
  }
  else if (res < 0)
    return false;

  read = static_cast<size_t>(res);
  return true;
}

bool TCPSocket::write(const uint8_t* buf, const size_t buf_len, size_t& written)
{
  written = 0;

  if (state_ != SocketState::Connected)
  {
    RCLCPP_ERROR(rclcpp::get_logger("PP"),"Attempt to write on a non-connected socket");
    return false;
  }

  size_t remaining = buf_len;

  // handle partial sends
  while (written < buf_len)
  {
    ssize_t sent = ::send(socket_fd_, buf + written, remaining, 0);

    if (sent <= 0)
    {
      RCLCPP_ERROR(rclcpp::get_logger("PP"),"Sending data through socket failed.");
      return false;
    }

    written += sent;
    remaining -= sent;
  }

  return true;
}


