// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { createI18n } from "vue-i18n";
import zhCN from "./zh-CN.js";
import enUS from "./en-US.js";

export default createI18n({ legacy: false, locale: navigator.language.startsWith("zh") ? "zh-CN" : "en-US", fallbackLocale: "en-US", messages: { "zh-CN": zhCN, "en-US": enUS } });