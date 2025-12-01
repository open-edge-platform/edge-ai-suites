/*******************************************************************************
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#pragma once

#include <dlstreamer/gst/videoanalytics/region_of_interest.h>

typedef struct _GstAnalyticsODMtdData GstAnalyticsODMtdData;
struct _GstAnalyticsODMtdData {
    GQuark object_type;
    gint x;
    gint y;
    gint w;
    gint h;
    gfloat r;
    gfloat location_confidence_lvl;
};

namespace GVA {

/**
 * @brief Extended RegionOfInterest class that provides access to internal metadata
 */
class ExtendedRegionOfInterest : public GVA::RegionOfInterest {
  public:
    /**
     * @brief Construct ExtendedRegionOfInterest from RegionOfInterest
     * @param roi RegionOfInterest object
     */
    ExtendedRegionOfInterest(const GVA::RegionOfInterest &roi) : GVA::RegionOfInterest(roi) {
    }

    /**
     * @brief Get access to the object detection metadata
     * @return Reference to _od_meta
     */
    const GstAnalyticsODMtd &get_od_meta() const {
        return _od_meta;
    }
};

} // namespace GVA

inline GstAnalyticsODMtdData *get_mtd_data_from_roi(const GVA::RegionOfInterest &roi) {
    GVA::ExtendedRegionOfInterest ext_roi(roi);
    GstAnalyticsODMtd od_meta = ext_roi.get_od_meta();
    return (GstAnalyticsODMtdData *)gst_analytics_relation_meta_get_mtd_data(od_meta.meta, od_meta.id);
}
