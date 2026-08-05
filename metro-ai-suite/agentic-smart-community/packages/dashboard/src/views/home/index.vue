<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="home-layout-shell">
    <div class="home-layout" :class="{ 'chat-collapsed': !isChatOpen }">
      <div class="layout-panel left-panel">
        <AppliancesMenu :selected-date="selectedDate" />
      </div>
      <div class="layout-panel center-panel">
        <VideoMonitorPanel
          :selected-date="selectedDate"
          @update:selected-date="handleSelectedDateChange"
        />
      </div>
      <div v-if="isChatOpen" class="layout-panel right-panel">
        <Chatqna @collapse="isChatOpen = false" />
      </div>

      <button
        v-else
        class="chat-trigger"
        type="button"
        :title="$t('chat.expandPanel')"
        @click="isChatOpen = true"
      >
        <span class="chat-trigger-icon vertical-center">
          <MessageOutlined />
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import dayjs, { type Dayjs } from "dayjs";
import { ref } from "vue";
import { MessageOutlined } from "@ant-design/icons-vue";
import { AppliancesMenu, Chatqna, VideoMonitorPanel } from "./components/index";

const selectedDate = ref<Dayjs>(dayjs());
const isChatOpen = ref(true);

const handleSelectedDateChange = (value: Dayjs) => {
  selectedDate.value = value;
};
</script>

<style scoped lang="less">
.home-layout-shell {
  width: 100%;
  height: 100%;
  overflow-x: auto;
  overflow-y: hidden;
}

.home-layout {
  position: relative;
  height: 100%;
  min-width: 1200px;
  display: grid;
  grid-template-columns: 300px minmax(0, 4fr) minmax(0, 3fr);
  gap: 12px;
  padding: 12px;
  background: var(--surface-app-bg);
  box-sizing: border-box;
}

/* Chat collapsed: the center video panel reclaims the right column's width. */
.home-layout.chat-collapsed {
  grid-template-columns: 300px minmax(0, 1fr);
}

/* Reopen tab — mirrors the Router card's monitor-trigger, docked to the right edge. */
.chat-trigger {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  z-index: 3;
  display: inline-flex;
  width: 38px;
  height: 52px;
  padding: 0;
  border: 1px solid
    color-mix(in srgb, var(--color-primary) 18%, var(--border-main-color) 82%);
  border-right: none;
  border-radius: 16px 0 0 16px;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--bg-content-color) 98%, transparent) 0%,
    color-mix(in srgb, var(--color-primaryBg) 24%, var(--bg-content-color) 76%)
      100%
  );
  color: var(--color-primary);
  box-shadow: 10px 14px 30px var(--bg-gradient-shadow);
  backdrop-filter: blur(14px);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

.chat-trigger::before {
  content: "";
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--color-primary) 78%, var(--color-white) 22%) 0%,
    var(--color-primary) 100%
  );
  opacity: 0.9;
}

.chat-trigger:hover {
  transform: translateY(-50%) translateX(-4px);
  border-color: color-mix(
    in srgb,
    var(--color-primary) 34%,
    var(--border-main-color) 66%
  );
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--bg-content-color) 100%, transparent) 0%,
    color-mix(in srgb, var(--color-primaryBg) 34%, var(--bg-content-color) 66%)
      100%
  );
  color: var(--color-primary-hover);
  box-shadow: 14px 18px 32px var(--bg-gradient-shadow);
}

.chat-trigger-icon {
  position: relative;
  width: 100%;
  height: 100%;
  font-size: 18px;
  line-height: 1;
}

.layout-panel {
  min-width: 0;
  min-height: 0;
}

.center-panel,
.right-panel {
  height: 100%;
}

.center-panel {
  display: block;
}

.right-panel {
  overflow: hidden;
  border-radius: 24px;
  border: 1px solid var(--border-primary);
  background: var(--surface-panel-bg);
}
</style>
