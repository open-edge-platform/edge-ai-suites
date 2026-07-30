<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="token-saving-card">
    <section class="totals-panel">
      <div class="section-heading">
        <div class="section-title">{{ t("monitor.modelTotals") }}</div>
        <div class="section-actions">
          <a-tooltip :title="t('monitor.refresh')">
            <button
              class="action-button"
              type="button"
              :disabled="isRefreshing || isResetting"
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
              class="action-button action-danger"
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

      <section class="overall-panelsection-card">
        <div v-if="routerStatus === 'not_configured'" class="router-status">
          {{ t("monitor.routerNotConfigured") }}
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
              <span class="metric-card-value">{{ cloudTotalText }}</span>
            </div>
          </div>

          <div class="compression-ring-card inline-chart">
            <div class="compression-ring-wrap">
              <svg
                class="compression-ring"
                viewBox="0 0 120 120"
                aria-hidden="true"
              >
                <circle class="compression-ring-track" cx="60" cy="60" r="46" />
                <circle
                  class="compression-ring-progress local"
                  cx="60"
                  cy="60"
                  r="46"
                  :stroke-dasharray="localRingDasharray"
                  :stroke-dashoffset="0"
                />
                <circle
                  class="compression-ring-progress cloud"
                  cx="60"
                  cy="60"
                  r="46"
                  :stroke-dasharray="cloudRingDasharray"
                  :stroke-dashoffset="cloudRingDashOffset"
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
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  RedoOutlined,
  SyncOutlined,
  CloseOutlined,
} from "@ant-design/icons-vue";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  getTokenStats,
  getTaskTokens,
  requestTokenRest,
} from "@/api/smartHome";

const props = withDefaults(
  defineProps<{
    embedded?: boolean;
    embeddedClosable?: boolean;
    selectedDate: string;
    selectedSourceId: string;
  }>(),
  {
    embedded: false,
    embeddedClosable: false,
    selectedDate: "",
    selectedSourceId: "",
  },
);
const emit = defineEmits<{
  close: [];
}>();

interface TokenModelMetrics {
  total_tokens: number;
}

interface OverallDisplayMetrics {
  total_tokens: number;
}

interface TaskTokenMetrics {
  total_tokens: number;
}

interface MonitorData {
  token_metrics: {
    local_model: TokenModelMetrics;
    cloud_model: TokenModelMetrics;
    overall: OverallDisplayMetrics;
  };
}

const POLL_INTERVAL = 1000;
const embedded = computed(() => props.embedded);
const embeddedClosable = computed(() => props.embeddedClosable);

const defaultMonitorData = (): MonitorData => ({
  token_metrics: {
    local_model: { total_tokens: 0 },
    cloud_model: { total_tokens: 0 },
    overall: { total_tokens: 0 },
  },
});

const defaultTaskTokenData = (): TaskTokenMetrics => ({
  total_tokens: 0,
});

const { t, locale } = useI18n();

const monitorData = ref<MonitorData>(defaultMonitorData());
const taskTokenData = ref<TaskTokenMetrics>(defaultTaskTokenData());
const isRefreshing = ref(false);
const isResetting = ref(false);
const routerStatus = ref<"configured" | "not_configured" | "unavailable">(
  "configured",
);
let pollTimer: number | undefined;

const numberFormatter = computed(
  () =>
    new Intl.NumberFormat(locale.value.startsWith("zh") ? "zh-CN" : "en-US"),
);

const formatNumber = (value: number) => numberFormatter.value.format(value);
const formatCompactNumber = (value: number) => {
  const absValue = Math.abs(value);

  if (absValue >= 1000000000) {
    return `${(value / 1000000000).toFixed(1)}B`;
  }

  if (absValue >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }

  if (absValue >= 1000) {
    return `${(value / 1000).toFixed(1)}K`;
  }

  return formatNumber(value);
};
const formatPercent = (value: number) => `${value.toFixed(1)}%`;
const normalizeNumber = (value: unknown, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizeMonitorData = (payload: any): MonitorData => {
  const stats =
    payload?.data && typeof payload.data === "object" ? payload.data : payload;

  return {
    token_metrics: {
      local_model: {
        total_tokens: normalizeNumber(
          stats?.token_metrics?.local_model?.total_tokens,
        ),
      },
      cloud_model: {
        total_tokens: normalizeNumber(
          stats?.token_metrics?.cloud_model?.total_tokens,
        ),
      },
      overall: {
        total_tokens: normalizeNumber(
          stats?.token_metrics?.overall?.total_tokens,
        ),
      },
    },
  };
};

const normalizeTaskTokenData = (payload: any): TaskTokenMetrics => {
  const stats =
    payload?.data && typeof payload.data === "object" ? payload.data : payload;

  return {
    total_tokens: normalizeNumber(stats?.total_tokens),
  };
};

const fetchTaskTokenStats = async () => {
  if (!props.selectedDate || !props.selectedSourceId) {
    return defaultTaskTokenData();
  }

  const response = await getTaskTokens({
    date: props.selectedDate,
    source_id: props.selectedSourceId,
  });

  return normalizeTaskTokenData(response);
};

const fetchStats = async (showRefreshing = false) => {
  if (showRefreshing) {
    isRefreshing.value = true;
  }
  try {
    const [response, taskResponse] = await Promise.all([
      getTokenStats(),
      fetchTaskTokenStats(),
    ]);
    routerStatus.value =
      response?.status === "not_configured"
        ? "not_configured"
        : response?.status === "unavailable"
          ? "unavailable"
          : "configured";
    monitorData.value = normalizeMonitorData(response);
    taskTokenData.value = taskResponse;
  } catch {
    routerStatus.value = "unavailable";
    monitorData.value = defaultMonitorData();
    taskTokenData.value = defaultTaskTokenData();
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
  () =>
    monitorData.value.token_metrics.local_model.total_tokens +
    taskTokenData.value.total_tokens,
);
const cloudTotal = computed(
  () => monitorData.value.token_metrics.cloud_model.total_tokens,
);
const derivedOverallTotal = computed(() => localTotal.value + cloudTotal.value);
const overallTotal = computed(() => {
  const backendOverall = monitorData.value.token_metrics.overall.total_tokens;
  return backendOverall > 0
    ? backendOverall + taskTokenData.value.total_tokens
    : derivedOverallTotal.value;
});

const localTotalText = computed(() => formatCompactNumber(localTotal.value));
const cloudTotalText = computed(() => formatCompactNumber(cloudTotal.value));
const overallTotalText = computed(() =>
  formatCompactNumber(overallTotal.value),
);

const localShareOfOverall = computed(() => {
  if (overallTotal.value <= 0) {
    return 0;
  }

  return (localTotal.value / overallTotal.value) * 100;
});

const cloudShareOfOverall = computed(() => {
  if (overallTotal.value <= 0) {
    return 0;
  }

  return (cloudTotal.value / overallTotal.value) * 100;
});

const localShareText = computed(() => formatPercent(localShareOfOverall.value));
const ringRadius = 46;
const ringCircumference = 2 * Math.PI * ringRadius;
const localRingLength = computed(
  () => (ringCircumference * localShareOfOverall.value) / 100,
);
const cloudRingLength = computed(
  () => (ringCircumference * cloudShareOfOverall.value) / 100,
);
const localRingDasharray = computed(
  () => `${localRingLength.value} ${ringCircumference}`,
);
const cloudRingDasharray = computed(
  () => `${cloudRingLength.value} ${ringCircumference}`,
);
const cloudRingDashOffset = computed(() => -localRingLength.value);

const handleManualRefresh = async () => {
  if (isRefreshing.value || isResetting.value) {
    return;
  }

  await fetchStats(true);
};

const handleReset = async () => {
  if (
    isRefreshing.value ||
    isResetting.value ||
    routerStatus.value === "not_configured"
  ) {
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

const handleClose = () => {
  emit("close");
};

onMounted(() => {
  void fetchStats(true);
  startPolling();
});

watch(
  () => [props.selectedDate, props.selectedSourceId],
  () => {
    void fetchStats(true);
  },
);

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<style scoped lang="less">
.token-saving-card {
  width: 100%;
  min-width: 0;
}

.router-status {
  margin-bottom: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border-main-color);
  border-radius: 10px;
  color: var(--font-tip-color);
  font-size: 12px;
  text-align: center;
}

.section-actions {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.action-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-main-color);
  border-radius: 10px;
  background: var(--bg-content-color);
  color: var(--font-text-color);
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.action-danger {
  color: var(--color-error);
}

.action-button:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: var(--border-info);
}

.close-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: 1px solid var(--border-main-color);
  border-radius: 10px;
  background: var(--bg-content-color);
  color: var(--font-text-color);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease;
}

.close-button:hover {
  transform: translateY(-1px);
  border-color: var(--border-info);
}

.action-icon.spinning {
  animation: spin 0.9s linear infinite;
}

.totals-panel {
  padding: 0;
  background: transparent;
  border: 0;
  box-shadow: none;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.section-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--font-main-color);
}

.compression-dashboard {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.compression-ring-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 12px;
  min-width: 0;
  padding: 16px 14px;
  border-radius: 20px;
  border: 1px solid
    color-mix(in srgb, var(--border-primary) 72%, var(--border-info));
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--color-successBg) 96%, transparent),
    color-mix(in srgb, var(--color-errorBg) 94%, transparent)
  );
  box-shadow: 0 14px 28px
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
  border-color: color-mix(
    in srgb,
    var(--border-primary) 78%,
    var(--border-main-color) 22%
  );
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--color-successBg) 32%, var(--surface-card-bg) 68%),
    color-mix(in srgb, var(--color-errorBg) 18%, var(--surface-card-bg) 82%)
  );
  box-shadow: 0 10px 20px
    color-mix(in srgb, var(--bg-box-shadow) 42%, transparent);
  .total-token {
    position: absolute;
    right: 16px;
    top: 16px;
    color: var(--font-tip-color);
    display: flex;
    font-size: 12px;
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
  stroke: var(--color-error);
}

.compression-ring-progress {
  stroke-linecap: round;
  transition:
    stroke-dasharray 0.35s ease,
    stroke-dashoffset 0.35s ease;
}

.compression-ring-progress.local {
  stroke: var(--color-success);
  filter: drop-shadow(0 6px 10px rgba(23, 153, 88, 0.18));
}

.compression-ring-progress.cloud {
  stroke: var(--color-error);
  filter: drop-shadow(0 6px 10px rgba(225, 90, 67, 0.18));
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
  color: var(--color-success);
}

.compression-ring-caption {
  max-width: 84px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--font-main-color);
}

.compression-metrics-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.metric-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--border-main-color);
  box-shadow: 0 10px 20px
    color-mix(in srgb, var(--bg-box-shadow) 40%, transparent);
}

.metric-card-label {
  font-size: 13px;
  font-weight: 600;
}

.metric-card-value {
  font-size: 32px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: -0.04em;
}
.local-wrap {
  border: 1px solid
    color-mix(in srgb, var(--color-success) 20%, var(--border-main-color) 80%);
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--color-successBg) 76%, var(--bg-content-color) 24%)
      0%,
    color-mix(in srgb, var(--bg-content-color) 90%, var(--color-successBg) 10%)
      100%
  );
  color: var(--color-success);
}
.cloud-wrap {
  border-color: color-mix(
    in srgb,
    var(--color-error) 22%,
    var(--border-main-color) 78%
  );

  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--color-errorBg) 76%, var(--bg-content-color) 24%) 0%,
    color-mix(in srgb, var(--bg-content-color) 90%, var(--color-errorBg) 10%)
      100%
  );
  color: var(--color-error);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
