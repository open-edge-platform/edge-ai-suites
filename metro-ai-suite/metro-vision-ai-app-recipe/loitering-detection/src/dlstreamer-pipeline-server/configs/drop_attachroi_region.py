#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""gvapython element: drop gvaattachroi's own ROI from published metadata.

Placed right after gvadetect. gvaattachroi's attached ROI (used to crop
where gvadetect runs via inference-region=1) is left on the buffer
afterwards as a plain, unlabeled region - metaconvert serialises it into
the MQTT/table "objects" list exactly like a real detection (it even gets
its own id), just without a label/confidence, inflating object counts
with a non-object. This removes it from that JSON output and from this
pipeline's own gvametaconvert-and-earlier view of the frame.

It does NOT remove it from the rendered WebRTC video: DL Streamer Pipeline
Server's WebRTC frame destination runs a second, separate gvawatermark
outside this pipeline string entirely (see its "Final launch WebRTC
Streams" log line), and in this DLStreamer version both gvawatermark
instances draw from the raw GstAnalyticsRelationMeta object-detection
entries - which `frame.remove_region()` never touches (confirmed live via
debug logging: removal here succeeds every frame with zero exceptions, yet
the box still renders in the final stream). No public API exists to
remove an individual GstAnalyticsRelationMeta entry once added. The result
is a single thin, unlabeled outline matching gvaattachroi's crop rectangle
in the video - cosmetic only (it does not gate detection, which is
genuinely restricted) - visible whenever that rectangle's shape doesn't
already coincide with a drawn zone (e.g. the combined bounding box of
several file zones of different shapes; a single zone, or an operator's
own rectangle, exactly match it and hide it from view).
"""


class DropAttachRoi:
    def process_frame(self, frame):
        for roi in list(frame.regions()):
            if not roi.label():
                try:
                    frame.remove_region(roi)
                except RuntimeError:
                    pass
        return True
