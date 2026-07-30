// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { createApp } from "vue";
import App from "./App.vue";
import router from "./router/index.js";
import i18n from "./i18n/index.js";
import "./styles/tokens.css";
import "./styles/global.css";

createApp(App).use(router).use(i18n).mount("#app");