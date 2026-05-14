/*******************************************************************************
 * Copyright (C) 2020 Intel Corporation
 *
 * SPDX-License-Identifier: MIT
 ******************************************************************************/

#pragma once

#include "feature_toggling/ifeature_toggler.h"

#include <map>
#include <memory>
#include <type_traits>

namespace FeatureToggling {
namespace Runtime {

class RuntimeFeatureToggler : public Base::IFeatureToggler {
    std::map<std::string, bool> features;
    std::unique_ptr<Base::IOptionsReader> options_reader;

  public:
    RuntimeFeatureToggler() = default;

    void configure(const std::vector<std::string> &enabled_features) {
      for (auto feature_name : enabled_features) {
        features.emplace(feature_name, true);
      }
    }

    bool enabled(const std::string &id) {
      auto it = features.find(id);
      if (it == features.end()) {
        std::tie(it, std::ignore) = features.emplace(id, false);
      }
      return it->second;
    }
};

} // namespace Runtime
} // namespace FeatureToggling
