#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""gvapython element: only draw boxes for objects gvaanalytics put in a zone.

Placed after gvametaconvert (and before gvawatermark) in config.json's
pipelines. gvadetect/gvatrack/gvaanalytics still run full-frame — dropping
only the box here keeps tracking continuity (an object's track does not
reset when it leaves a zone) while the rendered video and the loiter table
agree on what is "detected": objects outside every zone (the config file's
Pathway/Driveway polygons as well as the console's own OperatorZone
rectangle) are not highlighted.

gvametaconvert already serialised this frame's zone membership into a JSON
message (an object has "dwell_times"/"zone_violations" only if gvaanalytics
matched it to a zone), so that message - not a second geometry check - is
the source of truth here for which track ids to keep.
"""

import json


class ZoneOnlyFilter:
    def process_frame(self, frame):
        in_zone_ids = set()
        for msg in frame.messages():
            try:
                data = json.loads(msg)
            except (TypeError, ValueError):
                continue
            for obj in data.get("objects", []):
                if obj.get("dwell_times") or obj.get("zone_violations"):
                    obj_id = obj.get("id")
                    if obj_id is not None:
                        in_zone_ids.add(obj_id)

        for roi in list(frame.regions()):
            if roi.object_id() not in in_zone_ids:
                try:
                    frame.remove_region(roi)
                except RuntimeError:
                    pass  # meta already detached by another consumer

        return True
