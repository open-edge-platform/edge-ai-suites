# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shim factory : registry-based factory for VMS and Analytics-App shims.

Vendors register themselves by name in ``_VMS_REGISTRY`` / ``_ANALYTICS_APP_REGISTRY``.
Adding a new VMS / Analytics-App is a one-line registration; no factory edits needed.
"""

from __future__ import annotations

from typing import Callable

import structlog

from plugin.base.interfaces import IAnalyticsAppShim, IVmsShim
from plugin.core.config import AppConfig, AnyCorAppConfig, VmsInstanceConfig
from vms_shim.frigate.shim import FrigateVmsShim
from vms_shim.nxwitness.shim import NxWitnessVmsShim
from analytics_app_shim.lvc import LiveCaptioningAnalyticsAppShim
from analytics_app_shim.object_detection import ObjectDetectionAnalyticsAppShim

logger = structlog.get_logger(__name__)


VmsShimBuilder = Callable[[VmsInstanceConfig], IVmsShim]
AnalyticsAppShimBuilder = Callable[[AnyCorAppConfig], IAnalyticsAppShim]

_VMS_REGISTRY: dict[str, VmsShimBuilder] = {
    "frigate": FrigateVmsShim,
    "nx_witness": NxWitnessVmsShim,
}

_ANALYTICS_APP_REGISTRY: dict[str, AnalyticsAppShimBuilder] = {
    "live_captioning": LiveCaptioningAnalyticsAppShim,
    "object_detection": ObjectDetectionAnalyticsAppShim,
}


def register_vms(vendor: str, builder: VmsShimBuilder) -> None:
    """Register a new VMS vendor → shim constructor."""
    _VMS_REGISTRY[vendor] = builder


def register_analytics_app(app_type: str, builder: AnalyticsAppShimBuilder) -> None:
    """Register a new Analytics App type → shim constructor."""
    _ANALYTICS_APP_REGISTRY[app_type] = builder


class VmsShimSet:
    """Holds the single ``IVmsShim`` for one configured VMS instance."""

    def __init__(self, name: str, config: VmsInstanceConfig, vms_shim: IVmsShim):
        self.name = name
        self.config = config
        self.vms_shim = vms_shim


class ShimFactory:
    @staticmethod
    def create_vms_shims(config: AppConfig) -> list[VmsShimSet]:
        sets: list[VmsShimSet] = []
        for vms_inst in config.vms_instances:
            builder = _VMS_REGISTRY.get(vms_inst.vendor)
            if builder is None:
                logger.warning("unknown_vendor", vendor=vms_inst.vendor, name=vms_inst.name)
                continue
            sets.append(VmsShimSet(name=vms_inst.name, config=vms_inst, vms_shim=builder(vms_inst)))
            logger.info("vms_shim_created", name=vms_inst.name, vendor=vms_inst.vendor)
        return sets

    @staticmethod
    def create_analytics_app_shims(config: AppConfig) -> dict[str, IAnalyticsAppShim]:
        registry: dict[str, IAnalyticsAppShim] = {}
        for ca in config.analytics_apps:
            builder = _ANALYTICS_APP_REGISTRY.get(ca.type)
            if builder is None:
                logger.warning("unknown_analytics_app_type", type=ca.type)
                continue
            shim = builder(ca)
            if shim.app_id in registry:
                logger.warning("duplicate_analytics_app_id", app_id=shim.app_id)
                continue
            registry[shim.app_id] = shim
            logger.info("analytics_app_shim_created", app_id=shim.app_id)
        return registry

    @staticmethod
    def create_analytics_app_shim(config: AppConfig) -> IAnalyticsAppShim | None:
        registry = ShimFactory.create_analytics_app_shims(config)
        return next(iter(registry.values()), None)

