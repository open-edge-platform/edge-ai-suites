# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import logging


def get_logger(name):
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(name)
