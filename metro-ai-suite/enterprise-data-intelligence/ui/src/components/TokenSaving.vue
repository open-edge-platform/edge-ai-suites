<!--
  Copyright (C) 2026 Intel Corporation
  SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div
    :class="[
      embedded ? 'inline-assistant-root' : 'floating-assistant-root',
      { 'is-embedded': embedded },
    ]"
  >
    <button
      v-if="!embedded && !isOpen"
      class="floating-trigger flex-left"
      type="button"
      @click="openPanel"
    >
      <span class="trigger-icon-wrap vertical-center">
        <BarChartOutlined class="trigger-icon" />
      </span>
      <span class="trigger-copy">
        <span class="trigger-title">{{ t("monitor.title") }}</span>
      </span>
    </button>

    <div
      v-if="embedded || isOpen"
      ref="panelRef"
      class="assistant-panel"
      :class="{
        'is-dragging': isDragging,
        'is-pinned': isPinned,
        'is-embedded': embedded,
      }"
      :style="embedded ? undefined : panelStyle"
      @mouseenter="embedded ? undefined : handlePanelEnter"
      @mouseleave="embedded ? undefined : handlePanelLeave"
    >
      <div v-if="!embedded" class="pin-rail">
        <button
          class="rail-button vertical-center"
          :class="{ active: isPinned }"
          type="button"
          :title="t('monitor.pin')"
          @click="togglePinned"
        >
          <PushpinOutlined class="pin-icon" />
        </button>
      </div>
      <div class="panel-shell" :class="{ embedded }">
        <div class="panel-header flex-between" @mousedown="startDrag">
          <div class="header-brand flex-left">
            <span class="brand-icon vertical-center">
              <BarChartOutlined />
            </span>
            <div class="header-copy">
              <div class="eyebrow">{{ t("monitor.eyebrow") }}</div>
              <div class="panel-title">{{ t("monitor.title") }}</div>
            </div>
          </div>

          <div class="header-actions flex-left">
            <a-tooltip :title="t('monitor.refresh')">
              <button
                class="action-button vertical-center"
                type="button"
                @click="handleManualRefresh"
              >
                <SyncOutlined
                  class="action-icon"
                  :class="{ spinning: isRefreshing }"
                />
              </button>
            </a-tooltip>
            <a-tooltip :title="t('monitor.resetStats')">
              <button
                class="action-button action-danger vertical-center"
                type="button"
                :disabled="isRefreshing || isResetting"
                @click="handleReset"
              >
                <RedoOutlined
                  class="action-icon"
                  :class="{ spinning: isResetting }"
                />
              </button>
            </a-tooltip>
            <button
              v-if="!embedded || embeddedClosable"
              class="close-button vertical-center"
              type="button"
              :title="t('monitor.close')"
              @click="handleClose"
            >
              <CloseOutlined />
            </button>
          </div>
        </div>

        <div class="panel-scroll" :class="{ embedded }">
          <section class="overall-panelsection-card">
            <div class="section-heading compact-gap flex-between">
              <div>
                <div class="section-title">
                  {{ t("monitor.overallTotals") }}
                </div>
              </div>
            </div>

            <div class="compression-dashboard">
              <div class="compression-metrics-row">
                <div class="metric-card local-wrap">
                  <span class="metric-card-label">{{
                    t("monitor.localShort")
                  }}</span>
                  <span class="metric-card-value">{{ localTotalText }}</span>
                </div>

                <div class="metric-card cloud-wrap">
                  <span class="metric-card-label">
                    {{ t("monitor.cloudShort") }}
                  </span>
                  <span class="metric-card-value">{{
                    tokenConsumptionText
                  }}</span>
                </div>
              </div>

              <div class="compression-ring-card inline-chart">
                <div class="compression-ring-wrap">
                  <svg
                    class="compression-ring"
                    viewBox="0 0 120 120"
                    aria-hidden="true"
                  >
                    <circle
                      class="compression-ring-track"
                      cx="60"
                      cy="60"
                      r="46"
                    />
                    <circle
                      class="compression-ring-progress"
                      cx="60"
                      cy="60"
                      r="46"
                      :stroke-dasharray="ringCircumference"
                      :stroke-dashoffset="ringDashOffset"
                    />
                  </svg>
                  <div class="compression-ring-center">
                    <span class="compression-ring-value">
                      {{ localShareText }}</span
                    >
                    <span class="compression-ring-caption">{{
                      t("monitor.localShort")
                    }}</span>
                  </div>
                </div>
                <div class="total-token">
                  {{ t("monitor.overallTotals") }}:
                  <div class="total-value">
                    {{ overallTotalText }}
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section class="local-panel section-card">
            <div class="section-heading compact-gap flex-between">
              <div>
                <div class="section-title">{{ t("monitor.localTotals") }}</div>
              </div>
            </div>

            <div class="local-card local-wrap">
              <div class="local-card-head">
                <span class="totals-dot local"></span>
                <span class="local-card-label">{{
                  t("monitor.tokenConsumption")
                }}</span>
              </div>
              <div class="local-card-value">{{ localTotalText }}</div>
            </div>
          </section>

          <section class="section-card cloud-panel">
            <div class="section-heading compact-gap flex-between">
              <div>
                <div class="section-title">
                  {{ t("monitor.cloudProvider") }}
                </div>
              </div>
            </div>

            <div class="cloud-card cloud-consumption">
              <div class="cloud-summary-row">
                <div class="overall-stack-track">
                  <div
                    class="overall-segment cloud"
                    :style="{ width: `${compressionRateValue}%` }"
                  ></div>
                  <div
                    class="overall-segment saved"
                    :style="{ width: `${savedTokenRateValue}%` }"
                  ></div>
                </div>
                <div class="overall-copy cloud-summary-copy">
                  <span class="overall-label"> {{ t("common.total") }}: </span>
                  <span class="overall-value">{{ originalTokensText }}</span>
                </div>
              </div>
              <div class="overall-legend cloud-breakdown-list">
                <div class="cloud-breakdown-row consumption-row">
                  <span class="cloud-breakdown-main">
                    <span class="totals-dot cloud"></span>
                    <span class="cloud-breakdown-label">{{
                      t("monitor.tokenConsumption")
                    }}</span>
                  </span>
                  <span class="cloud-breakdown-percent">{{
                    compressionRateText
                  }}</span>
                  <span class="cloud-breakdown-value">{{
                    tokenConsumptionText
                  }}</span>
                </div>
                <div class="cloud-breakdown-row saved-row">
                  <span class="cloud-breakdown-main">
                    <span class="totals-dot saved"></span>
                    <span class="cloud-breakdown-label">
                      {{ t("monitor.savedTokenNoCostMain") }}
                    </span>
                  </span>
                  <span class="cloud-breakdown-percent">{{
                    savedTokenRateText
                  }}</span>
                  <span class="cloud-breakdown-value">{{
                    savedTokenText
                  }}</span>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  BarChartOutlined,
  CloseOutlined,
  PushpinOutlined,
  RedoOutlined,
  SyncOutlined,
} from "@ant-design/icons-vue";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { getTokenStats, requestTokenRest } from "@/api/knowledgeBase";

const props = withDefaults(
  defineProps<{
    embedded?: boolean;
    embeddedClosable?: boolean;
  }>(),
  {
    embedded: false,
    embeddedClosable: false,
  },
);
const emit = defineEmits<{
  close: [];
}>();

interface TotalInputMetrics {
  original_tokens: number;
  compressed_tokens: number;
  save_pct: number;
  rest_pct: number;
}

interface SystemAndToolsMetrics {
  original_tokens: number;
  compressed_tokens: number;
  saved_tokens: number;
  rest_pct: number;
}

interface TokenMetrics {
  total_tokens: number;
}

interface CompressionMetrics {
  total_input: TotalInputMetrics;
  system_and_tools: SystemAndToolsMetrics;
}

interface MonitorData {
  token_metrics: {
    local_model: TokenMetrics;
    cloud_model: TokenMetrics;
    overall: TokenMetrics;
  };
  compression: CompressionMetrics;
}

const POLL_INTERVAL = 2000;
const { t, locale } = useI18n();
const embedded = computed(() => props.embedded);
const embeddedClosable = computed(() => props.embeddedClosable);

const handleClose = () => {
  if (embedded.value) {
    emit("close");
    return;
  }

  closePanel();
};

const createDefaultMonitorData = (): MonitorData => ({
  token_metrics: {
    local_model: { total_tokens: 0 },
    cloud_model: { total_tokens: 0 },
    overall: { total_tokens: 0 },
  },
  compression: {
    total_input: {
      original_tokens: 0,
      compressed_tokens: 0,
      save_pct: 0,
      rest_pct: 0,
    },
    system_and_tools: {
      original_tokens: 0,
      compressed_tokens: 0,
      saved_tokens: 0,
      rest_pct: 0,
    },
  },
});

const monitorData = ref<MonitorData>(createDefaultMonitorData());
const isOpen = ref(false);
const isPinned = ref(false);
const isDragging = ref(false);
const isRefreshing = ref(false);
const isResetting = ref(false);
const panelRef = ref<HTMLElement | null>(null);

const PANEL_WIDTH = 488;
const PANEL_MIN_HEIGHT = 560;

const getInitialPosition = () => ({
  x: Math.max(16, window.innerWidth - PANEL_WIDTH - 24),
  y: Math.max(16, Math.round((window.innerHeight - PANEL_MIN_HEIGHT) / 2)),
});

const position = ref(getInitialPosition());

let dragOffsetX = 0;
let dragOffsetY = 0;
let pollTimer: number | undefined;
let closeTimer: number | undefined;

const numberFormatter = computed(
  () =>
    new Intl.NumberFormat(locale.value.startsWith("zh") ? "zh-CN" : "en-US"),
);

const formatNumber = (value: number) => numberFormatter.value.format(value);
const formatCompactDecimal = (
  value: number,
  divisor: number,
  suffix: string,
) => {
  const compactValue = value / divisor;
  const roundedValue = Math.round(compactValue);

  return `${formatNumber(roundedValue)}${suffix}`;
};

const formatCompactNumber = (value: number) => {
  const absValue = Math.abs(value);

  if (absValue >= 1000000000) {
    return formatCompactDecimal(value, 1000000000, "G");
  }

  if (absValue >= 1000000) {
    return formatCompactDecimal(value, 1000000, "M");
  }

  if (absValue >= 1000) {
    return formatCompactDecimal(value, 1000, "K");
  }

  return formatNumber(value);
};
const formatPercent = (value: number) => `${value.toFixed(1)}%`;

const normalizeNumber = (value: unknown, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeTokenMetrics = (metrics: any): TokenMetrics => ({
  total_tokens: normalizeNumber(metrics?.total_tokens),
});

const normalizeCompressionMetrics = (compression: any): CompressionMetrics => ({
  total_input: {
    original_tokens: normalizeNumber(compression?.total_input?.original_tokens),
    compressed_tokens: normalizeNumber(
      compression?.total_input?.compressed_tokens,
    ),
    save_pct: normalizeNumber(compression?.total_input?.save_pct),
    rest_pct: normalizeNumber(compression?.total_input?.rest_pct),
  },
  system_and_tools: {
    original_tokens: normalizeNumber(
      compression?.system_and_tools?.original_tokens,
    ),
    compressed_tokens: normalizeNumber(
      compression?.system_and_tools?.compressed_tokens,
    ),
    saved_tokens: normalizeNumber(compression?.system_and_tools?.saved_tokens),
    rest_pct: normalizeNumber(compression?.system_and_tools?.rest_pct),
  },
});

const normalizeMonitorData = (payload: any): MonitorData => {
  const stats =
    payload?.data && typeof payload.data === "object" ? payload.data : payload;

  return {
    token_metrics: {
      local_model: normalizeTokenMetrics(stats?.token_metrics?.local_model),
      cloud_model: normalizeTokenMetrics(stats?.token_metrics?.cloud_model),
      overall: normalizeTokenMetrics(stats?.token_metrics?.overall),
    },
    compression: normalizeCompressionMetrics(stats?.compression),
  };
};

const fetchStats = async (showRefreshing = false) => {
  if (showRefreshing) {
    isRefreshing.value = true;
  }

  try {
    const response = await getTokenStats();
    monitorData.value = normalizeMonitorData(response);
  } finally {
    isRefreshing.value = false;
  }
};

const startPolling = () => {
  stopPolling();
  pollTimer = window.setInterval(() => {
    void fetchStats();
  }, POLL_INTERVAL);
};

const stopPolling = () => {
  if (!pollTimer) {
    return;
  }

  window.clearInterval(pollTimer);
  pollTimer = undefined;
};

const localTotal = computed(
  () => monitorData.value.token_metrics.local_model.total_tokens,
);
const cloudTotal = computed(
  () => monitorData.value.token_metrics.cloud_model.total_tokens,
);
const overallTotal = computed(
  () => monitorData.value.token_metrics.overall.total_tokens,
);
const localTotalText = computed(() => formatCompactNumber(localTotal.value));
const overallTotalText = computed(() =>
  formatCompactNumber(overallTotal.value),
);

const localShareOfOverall = computed(() => {
  if (overallTotal.value <= 0) {
    return 0;
  }

  return (localTotal.value / overallTotal.value) * 100;
});

const localShareText = computed(() => formatPercent(localShareOfOverall.value));
const originalTokensText = computed(() =>
  formatCompactNumber(
    monitorData.value.compression.total_input.original_tokens,
  ),
);

const savedTokensTotal = computed(() => {
  const originalTokens =
    monitorData.value.compression.total_input.original_tokens;
  const compressedTokens =
    monitorData.value.compression.total_input.compressed_tokens;

  return Math.max(originalTokens - compressedTokens, 0);
});

const tokenConsumptionText = computed(() =>
  formatCompactNumber(cloudTotal.value),
);
const savedTokenText = computed(() =>
  formatCompactNumber(savedTokensTotal.value),
);
const compressionRateValue = computed(() => {
  const restPct = monitorData.value.compression.total_input.rest_pct;
  return restPct;
});
const savedTokenRateValue = computed(() => {
  const savePct = monitorData.value.compression.total_input.save_pct;
  return savePct;
});
const compressionRateText = computed(() =>
  formatPercent(compressionRateValue.value),
);
const savedTokenRateText = computed(() =>
  formatPercent(savedTokenRateValue.value),
);
const ringRadius = 46;
const ringCircumference = 2 * Math.PI * ringRadius;
const ringProgressValue = computed(() => localShareOfOverall.value);
const ringDashOffset = computed(
  () => ringCircumference * (1 - ringProgressValue.value / 100),
);

const panelStyle = computed(() => ({
  left: `${position.value.x}px`,
  top: `${position.value.y}px`,
}));

const clampPosition = (x: number, y: number) => {
  const panelWidth = panelRef.value?.offsetWidth ?? PANEL_WIDTH;
  const panelHeight = panelRef.value?.offsetHeight ?? PANEL_MIN_HEIGHT;
  const maxX = Math.max(16, window.innerWidth - panelWidth - 16);
  const maxY = Math.max(16, window.innerHeight - panelHeight - 16);

  position.value = {
    x: Math.min(Math.max(16, x), maxX),
    y: Math.min(Math.max(16, y), maxY),
  };
};

const handleManualRefresh = async () => {
  if (isRefreshing.value || isResetting.value) {
    return;
  }

  await fetchStats(true);
};

const handleReset = async () => {
  if (isRefreshing.value || isResetting.value) {
    return;
  }

  isResetting.value = true;
  try {
    await requestTokenRest();
    await fetchStats(true);
  } finally {
    isResetting.value = false;
  }
};

const openPanel = () => {
  if (embedded.value) {
    return;
  }

  clearCloseTimer();

  if (!isPinned.value) {
    position.value = getInitialPosition();
  }

  isOpen.value = true;
  clampPosition(position.value.x, position.value.y);
};

const closePanel = () => {
  if (embedded.value) {
    return;
  }

  isPinned.value = false;
  isOpen.value = false;
  stopDrag();
};

const clearCloseTimer = () => {
  if (!closeTimer) {
    return;
  }

  window.clearTimeout(closeTimer);
  closeTimer = undefined;
};

const scheduleClose = () => {
  if (embedded.value) {
    return;
  }

  if (isPinned.value) {
    return;
  }

  clearCloseTimer();
  closeTimer = window.setTimeout(() => {
    isOpen.value = false;
    stopDrag();
  }, 140);
};

const handlePanelEnter = () => {
  clearCloseTimer();
};

const handlePanelLeave = () => {
  scheduleClose();
};

const togglePinned = () => {
  if (embedded.value) {
    return;
  }

  isPinned.value = !isPinned.value;
  clearCloseTimer();
};

const handleDragMove = (event: MouseEvent) => {
  if (!isDragging.value) {
    return;
  }

  clampPosition(event.clientX - dragOffsetX, event.clientY - dragOffsetY);
};

const stopDrag = () => {
  if (embedded.value) {
    return;
  }

  isDragging.value = false;
  window.removeEventListener("mousemove", handleDragMove);
  window.removeEventListener("mouseup", stopDrag);
};

const startDrag = (event: MouseEvent) => {
  if (embedded.value) {
    return;
  }

  if (!isPinned.value) {
    return;
  }

  if ((event.target as HTMLElement | null)?.closest("button")) {
    return;
  }

  isDragging.value = true;
  dragOffsetX = event.clientX - position.value.x;
  dragOffsetY = event.clientY - position.value.y;
  window.addEventListener("mousemove", handleDragMove);
  window.addEventListener("mouseup", stopDrag);
};

const handleResize = () => {
  if (embedded.value) {
    return;
  }

  clampPosition(position.value.x, position.value.y);
};

onMounted(() => {
  window.addEventListener("resize", handleResize);
  void fetchStats(true);
  startPolling();
});

onBeforeUnmount(() => {
  clearCloseTimer();
  stopPolling();
  stopDrag();
  window.removeEventListener("resize", handleResize);
});
</script>

<style scoped lang="less">
.inline-assistant-root {
  width: 100%;
  height: 100%;
  min-height: 0;
}

.floating-assistant-root {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 1200;
}

.floating-trigger,
.assistant-panel {
  pointer-events: auto;
}

.inline-assistant-root,
.floating-assistant-root {
  --surface-base: var(--bg-content-color);
  --surface-soft: var(--surface-card-bg);
  --border-base: var(--border-main-color);
  --border-soft: var(--border-info);
  --border-accent: var(--border-primary);
  --track-base: var(--border-info);
  --shadow-base: var(--bg-gradient-shadow);
  --primary-accent: var(--color-primary);
  --primary-soft: var(--color-primarySoft);
  --success-accent: var(--color-success);
  --success-soft: var(--color-successSoft);
  --danger-accent: var(--color-error);
  --danger-soft: var(--color-errorSoft);
}

.floating-trigger {
  position: fixed;
  right: 0;
  top: 60%;
  gap: 10px;
  width: 74px;
  height: 68px;
  padding: 10px 14px 10px 12px;
  border: 1px solid var(--border-accent);
  border-right: none;
  border-radius: 20px 0 0 20px;
  background: var(--surface-base);
  color: var(--font-main-color);
  box-shadow: var(--shadow-base);
  cursor: pointer;
  overflow: hidden;
  transform: translateY(-50%);
  transition:
    width 0.22s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

.floating-trigger::before {
  content: "";
  position: absolute;
  inset: 0;
  background: var(--success-soft);
  opacity: 0.42;
  pointer-events: none;
}

.floating-trigger:hover,
.floating-trigger:focus-visible {
  width: 180px;
  transform: translateY(-50%);
  border-color: var(--success-accent);
  box-shadow: var(--shadow-base);
  outline: none;
}

.trigger-icon-wrap {
  position: relative;
  z-index: 1;
  flex: 0 0 44px;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: var(--success-soft);
  color: var(--success-accent);
  box-shadow: inset 0 0 0 1px var(--border-accent);
}

.trigger-icon {
  font-size: 20px;
}

.trigger-copy {
  position: relative;
  z-index: 1;
  min-width: 0;
  overflow: hidden;
}

.trigger-title {
  font-size: var(--font-size-14);
  font-weight: 700;
  line-height: 1;
  color: var(--font-main-color);
  white-space: nowrap;
  opacity: 0;
  transform: translateX(12px);
  transition:
    opacity 0.18s ease,
    transform 0.22s ease;
}

.floating-trigger:hover .trigger-title,
.floating-trigger:focus-visible .trigger-title {
  opacity: 1;
  transform: translateX(0);
}

.assistant-panel {
  position: fixed;
  display: flex;
  width: 520px;
  max-width: calc(100vw - 24px);
  min-height: 560px;
  animation: panel-enter 0.22s ease;
}

.assistant-panel.is-embedded {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  max-width: none;
  min-height: 0;
}

.pin-rail {
  width: 40px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 82px;
}

.rail-button {
  width: 30px;
  height: 68px;
  border: 1px solid var(--border-base);
  border-right: none;
  border-radius: 16px 0 0 16px;
  background: var(--surface-base);
  color: var(--font-tip-color);
  box-shadow: var(--shadow-base);
  cursor: pointer;
  transition: all 0.2s ease;
}

.rail-button.active {
  color: var(--success-accent);
  border-color: var(--border-accent);
  background: var(--success-soft);
}

.pin-icon {
  font-size: var(--font-size-15);
  transform: rotate(45deg);
}

.panel-shell {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-base);
  border-radius: 24px;
  background: var(--surface-base);
  box-shadow: none;
  overflow: hidden;
  backdrop-filter: blur(14px);
}

.panel-shell.embedded {
  flex: 0 0 380px;
  width: 380px;
  height: 100%;
  border-radius: 20px;
}

.panel-header {
  align-items: flex-start;
  gap: 14px;
  padding: 16px;
  background: var(--surface-soft);
  border-bottom: 1px solid var(--border-base);
  cursor: default;
}

.assistant-panel.is-pinned .panel-header {
  cursor: move;
}

.header-brand {
  align-items: flex-start;
  gap: 12px;
}

.brand-icon {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: var(--success-soft);
  border: 1px solid var(--border-accent);
  color: var(--success-accent);
  font-size: 20px;
}

.header-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.eyebrow {
  font-size: var(--font-size-11);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--font-tip-color);
}

.header-actions {
  gap: 8px;
}

.action-button,
.close-button {
  width: 30px;
  height: 30px;
  border: 1px solid var(--border-base);
  border-radius: 12px;
  background: var(--surface-base);
  color: var(--font-text-color);
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.action-danger {
  color: color-mix(
    in srgb,
    var(--danger-accent) 74%,
    var(--font-text-color) 26%
  );
  border-color: color-mix(
    in srgb,
    var(--danger-accent) 24%,
    var(--border-base) 76%
  );
  background: color-mix(
    in srgb,
    var(--danger-soft) 56%,
    var(--surface-base) 44%
  );
}

.action-button:hover:not(:disabled),
.close-button:hover {
  transform: translateY(-1px);
  border-color: var(--border-soft);
}

.action-icon.spinning {
  animation: spin 0.9s linear infinite;
}

.panel-scroll {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 620px;
  padding: 12px 14px 16px;
  overflow-y: auto;
}

.panel-scroll.embedded {
  flex: 1;
  min-height: 0;
  max-height: none;
  gap: 10px;
  padding: 8px 10px 10px;
  overflow: auto;
}

.assistant-panel.is-embedded .panel-header {
  padding: 12px;
}

.assistant-panel.is-embedded .header-brand {
  gap: 8px;
}

.assistant-panel.is-embedded .brand-icon {
  width: 32px;
  height: 32px;
  font-size: var(--font-size-16);
  border-radius: 10px;
}

.assistant-panel.is-embedded .header-copy {
  gap: 2px;
}

.assistant-panel.is-embedded .eyebrow {
  font-size: var(--font-size-10);
}

.assistant-panel.is-embedded .panel-title {
  font-size: var(--font-size-14);
  font-weight: 600;
}

.assistant-panel.is-embedded .action-button {
  width: 28px;
  height: 28px;
  border-radius: 10px;
}

.assistant-panel.is-embedded .header-actions {
  gap: 6px;
}

.assistant-panel.is-embedded .section-card {
  padding: 10px;
  border-radius: 16px;
}

.assistant-panel.is-embedded .local-card {
  padding: 12px 14px;
}

.assistant-panel.is-embedded .cloud-card {
  grid-template-columns: 90px minmax(0, 1fr);
  gap: 8px;
}

.assistant-panel.is-embedded .overall-value {
  font-size: 24px;
  color: var(--font-main-color);
}

.assistant-panel.is-embedded .compression-dashboard {
  gap: 10px;
}

.assistant-panel.is-embedded .compression-ring-card {
  padding: 6px 12px;
}

.assistant-panel.is-embedded .compression-ring-wrap {
  min-height: 135px;
}

.assistant-panel.is-embedded .section-heading {
  margin-bottom: 8px;
}

.assistant-panel.is-embedded .section-heading.compact-gap {
  margin-bottom: 6px;
}

.assistant-panel.is-embedded .section-title {
  font-size: var(--font-size-13);
}

.assistant-panel.is-embedded .overall-copy {
  gap: 4px;
}

.assistant-panel.is-embedded .cloud-summary-row {
  gap: 10px;
}

.assistant-panel.is-embedded .cloud-summary-copy .overall-label,
.assistant-panel.is-embedded .cloud-summary-copy .overall-value {
  font-size: var(--font-size-14);
}

.assistant-panel.is-embedded .cloud-summary-copy {
  padding: 8px 10px;
}

.assistant-panel.is-embedded .overall-stack {
  gap: 8px;
}

.assistant-panel.is-embedded .overall-legend {
  gap: 8px;
}

.assistant-panel.is-embedded .cloud-breakdown-row {
  padding: 10px 12px;
}

.assistant-panel.is-embedded .cloud-breakdown-label,
.assistant-panel.is-embedded .cloud-breakdown-percent,
.assistant-panel.is-embedded .cloud-breakdown-value {
  font-size: var(--font-size-13);
}

.section-card {
  padding: 14px;
  border-radius: 20px;
  background: var(--surface-base);
  border: 1px solid var(--border-base);
}

.section-heading {
  gap: 10px;
  margin-bottom: 12px;
}

.section-heading.compact-gap {
  margin-bottom: 10px;
}

.section-title {
  font-size: var(--font-size-14);
  font-weight: 700;
  color: var(--font-main-color);
}

.totals-label-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.totals-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.totals-dot.local {
  background: var(--success-accent);
}

.totals-dot.cloud {
  background: var(--danger-accent);
}
.totals-dot.saved {
  background: var(--primary-accent);
}

.totals-dot.overall {
  background: linear-gradient(
    90deg,
    var(--danger-accent) 0%,
    var(--danger-accent) 50%,
    var(--primary-accent) 50%,
    var(--primary-accent) 100%
  );
}

.totals-bar-track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--track-base);
}

.totals-bar-fill {
  height: 100%;
  border-radius: inherit;
}

.totals-bar-fill.local {
  background: var(--success-accent);
}

.totals-bar-fill.cloud {
  background: var(--danger-accent);
}

.cloud-card {
  display: grid;
  grid-template-columns: 156px minmax(0, 1fr);
  gap: 14px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid
    color-mix(in srgb, var(--border-soft) 64%, var(--border-base) 36%);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--surface-base) 84%, var(--success-soft) 16%) 0%,
    color-mix(in srgb, var(--surface-base) 90%, var(--danger-soft) 10%) 100%
  );
  box-shadow:
    0 8px 18px rgba(15, 23, 42, 0.05),
    0 2px 5px rgba(15, 23, 42, 0.035),
    inset 0 1px 0 rgba(255, 255, 255, 0.32);
}

.overall-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-size-12);
  color: var(--font-text-color);
  font-weight: 600;
}

.overall-value {
  font-size: 34px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: -0.03em;
  color: var(--color-primary-deep);
}

.cloud-card .overall-value {
  color: var(--danger-accent);
}

.cloud-card.cloud-consumption {
  display: flex;
  flex-direction: column;
  border: 1px solid
    color-mix(in srgb, var(--border-accent) 72%, var(--border-soft));
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--danger-soft) 78%, transparent),
    color-mix(in srgb, var(--primary-soft) 72%, transparent)
  );
  box-shadow: 0 12px 26px
    color-mix(in srgb, var(--bg-box-shadow) 75%, transparent);
}
.cloud-summary-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 100px;
  align-items: center;
  gap: 16px;
}

.cloud-summary-copy {
  .vertical-center;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--border-accent) 46%, transparent);
  background: color-mix(in srgb, var(--surface-base) 82%, transparent);
}

.cloud-summary-copy .overall-label {
  font-size: var(--font-size-12);
  letter-spacing: 0.02em;
  opacity: 0.78;
}

.cloud-summary-copy .overall-value {
  font-size: 20px;
  line-height: 1.1;
  letter-spacing: 0;
  font-weight: 800;
}

.overall-stack {
  .flex-column;
  justify-content: center;
  gap: 14px;
}

.overall-stack-track {
  display: flex;
  height: 16px;
  overflow: hidden;
  border-radius: 999px;
  border: 1px solid
    color-mix(in srgb, var(--border-soft) 70%, var(--border-base) 30%);
  background: var(--surface-soft);
  box-shadow: 0 8px 18px
    color-mix(in srgb, var(--bg-box-shadow) 90%, transparent);
}

.overall-segment {
  height: 100%;
  border-radius: 0;
}

.overall-segment.saved {
  border-radius: 0 999px 999px 0;
  background: linear-gradient(
    90deg,
    var(--primary-accent) 0%,
    color-mix(in srgb, var(--primary-accent) 72%, var(--color-white) 28%) 100%
  );
}

.overall-segment.cloud {
  border-radius: 999px 0 0 999px;
  background: var(--danger-accent);
}

.overall-legend {
  .flex-column;
  gap: 10px;
}

.cloud-breakdown-list {
  gap: 10px;
}

.cloud-breakdown-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid transparent;
  font-size: var(--font-size-13);
  font-weight: 600;
}

.cloud-breakdown-main {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.cloud-breakdown-label {
  min-width: 0;
  color: var(--font-main-color);
  font-size: var(--font-size-14);
}

.cloud-breakdown-percent {
  color: var(--font-text-color);
  font-size: var(--font-size-14);
  font-weight: 700;
}

.cloud-breakdown-value {
  font-size: 20px;
  line-height: 1;
  font-weight: 700;
  text-align: right;
  letter-spacing: -0.02em;
}

.consumption-row {
  color: var(--danger-accent);
  background: color-mix(
    in srgb,
    var(--danger-soft) 72%,
    var(--surface-base) 28%
  );
  border-color: color-mix(
    in srgb,
    var(--border-accent) 52%,
    var(--border-base) 48%
  );
}

.saved-row {
  color: var(--primary-accent);
  background: color-mix(
    in srgb,
    var(--primary-soft) 64%,
    var(--surface-base) 36%
  );
  border-color: color-mix(
    in srgb,
    var(--primary-accent) 24%,
    var(--border-base) 76%
  );
}

.local-panel {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--success-soft) 54%, var(--surface-base) 46%) 0%,
    var(--surface-base) 100%
  );
}
.cloud-panel {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--danger-soft) 58%, var(--surface-base) 42%) 0%,
    color-mix(in srgb, var(--danger-soft) 22%, var(--surface-base) 78%) 100%
  );
}

.local-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 18px;
}

.local-card-head {
  .flex-left;
  gap: 8px;
  min-width: 0;
}

.local-card-label {
  font-size: var(--font-size-13);
  font-weight: 600;
  color: var(--font-text-color);
}

.local-card-value {
  flex-shrink: 0;
  font-size: 32px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--success-accent);
}

.local-card-track {
  height: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(
    in srgb,
    var(--success-soft) 40%,
    var(--track-base) 60%
  );
}

.local-card-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    var(--success-accent) 0%,
    color-mix(in srgb, var(--success-accent) 72%, var(--color-white) 28%) 100%
  );
}

.compression-dashboard {
  .flex-column;
  gap: 12px;
}

.compression-metrics-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  .flex-column;
  gap: 10px;
  min-width: 0;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--border-base);
}

.metric-card-label {
  font-size: var(--font-size-13);
  font-weight: 600;
}

.metric-card-label-sub {
  font-size: var(--font-size-11);
  font-weight: 500;
  opacity: 0.72;
}

.metric-card-value {
  font-size: 32px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.saved-token-card {
  border-color: color-mix(
    in srgb,
    var(--primary-accent) 22%,
    var(--border-base) 78%
  );
  background: color-mix(
    in srgb,
    var(--primary-soft) 82%,
    var(--surface-base) 18%
  );
  color: var(--primary-accent);
}

.compression-ring-card {
  .flex-column;
  justify-content: center;
  gap: 12px;
  min-width: 0;
  padding: 16px 14px;
  border-radius: 20px;
  border: 1px solid
    color-mix(in srgb, var(--border-accent) 72%, var(--border-soft));
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--success-soft) 96%, transparent),
    color-mix(in srgb, var(--danger-soft) 94%, transparent)
  );
  box-shadow: 0 12px 26px
    color-mix(in srgb, var(--bg-box-shadow) 75%, transparent);
}

.compression-ring-card.inline-chart {
  display: grid;
  place-items: center;
  flex: 1 1 0;
  width: auto;
  min-width: 0;
  height: 100%;
  position: relative;
  .total-token {
    position: absolute;
    right: 16px;
    top: 16px;
    color: var(--font-tip-color);
    display: flex;
    font-size: var(--font-size-12);
    .total-value {
      color: var(--font-main-color);
      padding-left: 4px;
    }
  }
}

.compression-ring-wrap {
  position: relative;
  display: grid;
  place-items: center;
  width: 120px;
  min-height: 160px;
  cursor: pointer;
  margin: 0 auto;
}

.compression-ring {
  width: 120px;
  height: 120px;
  transform: rotate(-90deg);
}

.compression-ring-track,
.compression-ring-progress {
  fill: none;
  stroke-width: 10;
}

.compression-ring-track {
  stroke: var(--danger-accent);
}

.compression-ring-progress {
  stroke: var(--success-accent);
  stroke-linecap: round;
  transition: stroke-dashoffset 0.35s ease;
  filter: drop-shadow(
    0 6px 10px color-mix(in srgb, var(--success-accent) 18%, transparent)
  );
}

.compression-ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  text-align: center;
}

.compression-ring-value {
  font-size: 22px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--success-accent);
}

.compression-ring-caption {
  max-width: 84px;
  font-size: var(--font-size-12);
  font-weight: 600;
  line-height: 1.3;
  color: var(--font-main-color);
}

@keyframes panel-enter {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.98);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
.local-wrap {
  border: 1px solid
    color-mix(in srgb, var(--success-accent) 20%, var(--border-base) 80%);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--success-soft) 76%, var(--surface-base) 24%) 0%,
    color-mix(in srgb, var(--surface-base) 90%, var(--success-soft) 10%) 100%
  );
  color: var(--success-accent);
}
.cloud-wrap {
  border-color: color-mix(
    in srgb,
    var(--danger-accent) 22%,
    var(--border-base) 78%
  );

  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--danger-soft) 76%, var(--surface-base) 24%) 0%,
    color-mix(in srgb, var(--surface-base) 90%, var(--danger-soft) 10%) 100%
  );
  color: var(--danger-accent);
}
.saved-wrap {
  border-color: color-mix(
    in srgb,
    var(--primary-accent) 22%,
    var(--border-base) 78%
  );
  background: color-mix(
    in srgb,
    var(--primary-soft) 82%,
    var(--surface-base) 18%
  );
  color: var(--primary-accent);
}
</style>
