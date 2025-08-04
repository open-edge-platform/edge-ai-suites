#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions
# and limitations under the License.

import numpy as np


class PCA:
    def __init__(self, n_components=1):
        self.mean = None
        self.eig_vectors = None
        self.n_components = n_components

    def build(self, x):
        m = np.mean(x, axis=0)
        xm = x - m
        cov_mat = np.cov(xm.T)
        eig_values, eig_vectors = np.linalg.eig(cov_mat)

        idx = np.argsort(eig_values)[::-1]
        eig_vectors = eig_vectors[:, idx]
        v = eig_vectors[:, :self.n_components]
        projection = xm.dot(v)

        self.eig_vectors = eig_vectors
        self.mean = m
        return projection

    def project(self, x):
        xm = x - self.mean
        v = self.eig_vectors[:, :self.n_components]
        return xm.dot(v)

    def iproject(self, z):
        v = self.eig_vectors[:, :self.n_components]
        x = z * v.T + self.mean
        return x
