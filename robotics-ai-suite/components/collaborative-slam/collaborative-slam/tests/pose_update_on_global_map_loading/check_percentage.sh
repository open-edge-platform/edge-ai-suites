#!/bin/bash
# Copyright (C) 2022 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
cat /tmp/log-tracker1.txt | grep 'UnivLoc (connected) got' | grep 'images in past' | while read -r line ; do
    if [ $(echo $line | awk '{print $19}' | tr -dc '0-9.' | awk '{ print int($1) }') -ge 90 ]
    then
       echo "OK"
    else
       echo "NOK"
       echo $line
       exit 1
    fi
done
