#!/bin/bash
set -e

vcs import < rvc.repos src
sudo apt-get update
rosdep update
rosdep install --from-paths src --ignore-src -y
