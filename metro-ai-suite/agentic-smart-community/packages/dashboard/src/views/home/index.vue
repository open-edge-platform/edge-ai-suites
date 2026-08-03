<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="home-layout-shell">
    <div class="home-layout">
      <div class="layout-panel left-panel">
        <AppliancesMenu :selected-date="selectedDate" />
      </div>
      <div class="layout-panel center-panel">
        <VideoMonitorPanel
          :selected-date="selectedDate"
          @update:selected-date="handleSelectedDateChange"
        />
      </div>
      <div class="layout-panel right-panel">
        <Chatqna />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import dayjs, { type Dayjs } from "dayjs";
import { ref } from "vue";
import { AppliancesMenu, Chatqna, VideoMonitorPanel } from "./components/index";

const selectedDate = ref<Dayjs>(dayjs());

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
  height: 100%;
  min-width: 1200px;
  display: grid;
  grid-template-columns: 300px minmax(0, 4fr) minmax(0, 3fr);
  gap: 12px;
  padding: 12px;
  background: var(--surface-app-bg);
  box-sizing: border-box;
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
