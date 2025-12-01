/*******************************************************************************
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#include "gvaposturedetect.h"
#include "gvareid.h"
#include "gvaroifilter.h"

static gboolean plugin_init(GstPlugin *plugin) {
    gboolean result = TRUE;

    result &= gst_element_register(plugin, "gvaposturedetect", GST_RANK_NONE, GST_TYPE_POSTURE_DETECT);
    result &= gst_element_register(plugin, "gvaroifilter", GST_RANK_NONE, GST_TYPE_ROI_FILTER);
    result &= gst_element_register(plugin, "gvareid", GST_RANK_NONE, GST_TYPE_REID);

    return result;
}

#ifndef PACKAGE
#define PACKAGE "gvasmartclassroom"
#endif

GST_PLUGIN_DEFINE(GST_VERSION_MAJOR, GST_VERSION_MINOR, gvasmartclassroom, "Smart Classroom Plugins", plugin_init,
                  "1.0.0", "MIT", PACKAGE, "https://github.com/open-edge-platform")
