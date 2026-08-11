<!--
  Copyright (C) 2026 Intel Corporation
  SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="home-layout">
    <section class="chat-pane">
      <Chatqna />
    </section>

    <button
      v-if="!isMonitorOpen"
      class="monitor-trigger"
      type="button"
      :title="t('monitor.title')"
      @click="openMonitor"
    >
      <span class="monitor-trigger-icon">
        <BarChartOutlined />
      </span>
    </button>

    <aside class="monitor-pane" :class="{ open: isMonitorOpen }">
      <TokenSaving embedded embedded-closable @close="closeMonitor" />
    </aside>
  </div>
</template>

<script setup lang="ts">
import { BarChartOutlined } from "@ant-design/icons-vue";
import { useI18n } from "vue-i18n";
import TokenSaving from "@/components/TokenSaving.vue";
import { Chatqna } from "./components/index";

const { t } = useI18n();
const isMonitorOpen = ref(false);

const openMonitor = () => {
  isMonitorOpen.value = true;
};

const closeMonitor = () => {
  isMonitorOpen.value = false;
};
</script>
<style scoped lang="less">
.home-layout {
  position: relative;
  height: 100%;
  min-height: 0;
  display: flex;
  padding: 12px;
  overflow: hidden;
  background: var(--bg-content-color);
}

.chat-pane,
.monitor-pane {
  min-height: 0;
  height: 100%;
}

.chat-pane {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  border-radius: 24px;
  background: var(--bg-content-color);
  border: 1px solid var(--border-main-color);
  transition: width 0.24s ease;
}

.monitor-pane {
  position: relative;
  width: 0;
  min-width: 0;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
  transition:
    width 0.24s ease,
    opacity 0.2s ease;
}

.monitor-pane.open {
  width: 380px;
  opacity: 1;
  pointer-events: auto;
  margin-left: 12px;
}

.monitor-trigger {
  position: absolute;
  top: 50%;
  right: 0;
  transform: translateY(-50%);
  z-index: 20;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 68px;
  padding: 0;
  border: 1px solid
    color-mix(in srgb, var(--color-primary) 18%, var(--color-white) 82%);
  border-right: none;
  border-radius: 16px 0 0 16px;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.98) 0%,
    color-mix(in srgb, var(--color-primaryBg) 24%, var(--color-white) 76%) 100%
  );
  color: var(--color-primary);
  box-shadow: -10px 14px 30px rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(14px);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

.monitor-trigger::before {
  content: "";
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(
    180deg,
    var(--color-primary-hover) 0%,
    var(--color-primary) 100%
  );
  opacity: 0.9;
}

.monitor-trigger:hover {
  transform: translateY(-50%) translateX(-4px);
  border-color: color-mix(
    in srgb,
    var(--color-primary) 34%,
    var(--color-white) 66%
  );
  background: linear-gradient(
    180deg,
    var(--color-primaryBg) 0%,
    color-mix(in srgb, var(--color-primaryBg) 34%, var(--color-white) 66%) 100%
  );
  color: var(--color-primary-hover);
  box-shadow: 0 12px 24px
    color-mix(in srgb, var(--bg-box-shadow) 100%, transparent);
}

.monitor-trigger-icon {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  padding-left: 3px;
  font-size: 18px;
  line-height: 1;
}

@media (max-width: 1024px) {
  .home-layout {
    padding-right: 12px;
    overflow-x: auto;
    overflow-y: hidden;
  }

  .chat-pane {
    flex: 1 0 640px;
  }

  .monitor-pane {
    position: relative;
    top: auto;
    right: auto;
    bottom: auto;
    width: 0;
    min-width: 0;
    opacity: 0;
    pointer-events: none;
    transition:
      width 0.24s ease,
      opacity 0.2s ease;
  }

  .monitor-pane.open {
    width: min(320px, calc(100vw - 48px));
    opacity: 1;
    pointer-events: auto;
    margin-left: 12px;
  }

  .monitor-trigger {
    right: 0;
  }
}

@media (max-width: 768px) {
  .chat-pane {
    flex-basis: 560px;
  }

  .monitor-trigger {
    width: 38px;
    height: 62px;
  }
}
</style>
