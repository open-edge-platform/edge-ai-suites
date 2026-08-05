// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
declare module "vue3-video-play/dist/index.mjs" {
  import type { DefineComponent, Plugin } from "vue";

  export const videoPlay: DefineComponent<Record<string, unknown>, {}, any>;

  const plugin: Plugin;
  export default plugin;
}
