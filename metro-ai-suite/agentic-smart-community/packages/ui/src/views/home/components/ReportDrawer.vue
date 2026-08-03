<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <a-drawer
    :open="true"
    :width="860"
    placement="right"
    root-class-name="report-drawer"
    @close="emit('close')"
  >
    <template #title>
      <div class="drawer-title-wrap flex-between">
        <div>
          <div class="drawer-title">
            {{ $t("smartHome.reportDrawerTitle") }}
          </div>
        </div>
        <div class="drawer-actions flex-left">
          <a-button
            class="drawer-generate-btn"
            size="small"
            :loading="generatingReport"
            @click="handleGenerate"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            {{ $t("smartHome.generateLatestReport") }}
          </a-button>
          <a-button
            class="drawer-export-btn"
            type="primary"
            size="small"
            @click="handleExport"
          >
            <template #icon>
              <DownloadOutlined />
            </template>
            {{ $t("smartHome.exportReport") }}
          </a-button>
        </div>
      </div>
    </template>

    <div class="report-drawer-body">
      <a-empty
        v-if="!drawerData.length"
        :description="$t('smartHome.reportNoContent')"
      />

      <template v-else>
        <div class="report-summary-bar flex-left">
          <div class="report-summary-chip">
            <span>{{ $t("smartHome.reportSelectedDate") }}:</span>
            <strong>{{ selectedDateDisplay }}</strong>
          </div>
          <div class="report-summary-chip">
            <span>{{ $t("smartHome.reportCountLabel") }}:</span>
            <strong>{{ drawerData.length }}</strong>
          </div>
          <div class="report-summary-chip" v-if="activeReport">
            <span>{{ $t("smartHome.reportCreatedAtLabel") }}:</span>
            <strong>{{ activeReport.created_at }}</strong>
          </div>
        </div>

        <div class="report-layout">
          <div class="report-list-panel">
            <div class="report-list-title">
              {{ $t("smartHome.reportListTitle") }}
            </div>
            <button
              v-for="report in drawerData"
              :key="report.id"
              class="report-list-item"
              :class="{ active: report.id === activeReport?.id }"
              type="button"
              @click="handleSelectReport(report.id)"
            >
              <div class="report-list-item-head flex-between">
                <strong>{{ report.report_date }}</strong>
                <span class="report-status-pill">{{
                  buildRecordStatus(report.status)
                }}</span>
              </div>
              <div class="report-list-meta">{{ report.created_at }}</div>
              <div class="report-list-counters">
                <span>
                  {{ $t("smartHome.reportEventCount") }}:
                  {{ report.event_count }}
                </span>
                <span>
                  {{ $t("smartHome.reportMotionCount") }}:
                  {{ report.motion_count }}
                </span>
              </div>
            </button>
          </div>

          <div class="report-content-panel flex-column" v-if="activeReport">
            <div class="report-hero">
              <div>
                <div class="report-hero-date">
                  {{ activeReport.report_date }}
                </div>
                <div class="report-hero-subtitle">
                  {{ $t("smartHome.reportModalSubtitle") }}
                </div>
              </div>
              <div class="report-hero-status">
                {{ buildRecordStatus(activeReport.status) }}
              </div>
            </div>

            <div class="report-metrics">
              <div
                v-for="metric in activeMetrics"
                :key="metric.label"
                class="report-metric flex-column"
              >
                <span class="report-metric-label">{{ metric.label }}</span>
                <strong class="report-metric-value">{{ metric.value }}</strong>
              </div>
            </div>

            <div class="report-markdown-panel">
              <div class="report-detail-title">
                {{ $t("smartHome.reportDetailSection") }}
              </div>
              <div
                class="intel-markdown report-markdown"
                v-html="activeReportHtml"
              ></div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons-vue";
import CustomRenderer from "@/utils/customRenderer";
import type { CameraReport } from "../type";
import { marked } from "marked";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{
  selectedDate: string;
  drawerData: CameraReport[];
  generatingReport?: boolean;
}>();

const emit = defineEmits<{
  close: [];
  export: [reports: CameraReport[]];
  generate: [];
}>();

const { t } = useI18n();
const internalActiveReportId = ref<number | null>(null);

const selectedDateDisplay = computed(() => {
  return `${t("smartHome.reportSelectedDate")} ${props.selectedDate}`;
});

const activeReport = computed(() => {
  return (
    props.drawerData.find(
      (report) => report.id === internalActiveReportId.value,
    ) ??
    props.drawerData[0] ??
    null
  );
});

const activeReportHtml = computed(() => {
  const reportText = activeReport.value?.report_text?.trim();

  if (!reportText) {
    return "";
  }

  return marked.parse(reportText, {
    async: false,
    breaks: true,
    gfm: true,
    renderer: CustomRenderer,
  }) as string;
});

const activeMetrics = computed(() => {
  if (!activeReport.value) {
    return [];
  }

  return [
    {
      label: t("smartHome.reportSelectedDate"),
      value: activeReport.value.report_date,
    },
    {
      label: t("smartHome.reportStatusLabel"),
      value: buildRecordStatus(activeReport.value.status),
    },
    {
      label: t("smartHome.reportEventCount"),
      value: String(activeReport.value.event_count),
    },
    {
      label: t("smartHome.reportMotionCount"),
      value: String(activeReport.value.motion_count),
    },
    {
      label: t("smartHome.reportPromptTokens"),
      value: String(activeReport.value.prompt_tokens),
    },
    {
      label: t("smartHome.reportCreatedAtLabel"),
      value: activeReport.value.created_at,
    },
  ];
});

const buildRecordStatus = (status: string) => {
  if (!status) {
    return "";
  }

  return status === "completed" ? t("smartHome.recordStatusCompleted") : status;
};

const handleSelectReport = (reportId: number) => {
  internalActiveReportId.value = reportId;
};

const handleExport = () => {
  emit("export", props.drawerData);
};

const handleGenerate = () => {
  emit("generate");
};

watch(
  () => props.drawerData,
  () => {
    internalActiveReportId.value = props.drawerData[0]?.id ?? null;
  },
  { immediate: true },
);
</script>

<style scoped lang="less">
.drawer-title-wrap {
  gap: 16px;
}

.drawer-actions {
  gap: 8px;
}

.drawer-title {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 700;
  color: var(--font-main-color);
}

.drawer-export-btn {
  border-radius: 12px;
}

.drawer-generate-btn {
  border-radius: 12px;
}

.report-drawer-body {
  .flex-column;
  gap: 16px;
  min-height: calc(100vh - 160px);
}

.report-summary-bar {
  gap: 12px;
  flex-wrap: wrap;
}

.report-summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: var(--color-primaryBg);
  border: 1px solid var(--border-primary);
  font-size: 12px;
  color: var(--font-tip-color);
}

.report-summary-chip strong {
  color: var(--font-main-color);
}

.report-layout {
  min-height: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  flex: 1;
}

.report-list-panel,
.report-content-panel {
  border-radius: 24px;
  background: var(--surface-panel-bg-strong);
  border: 1px solid var(--border-primary);
}

.report-list-panel {
  padding: 16px;
  .flex-column;
  gap: 12px;
  overflow: auto;
}

.report-list-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--font-main-color);
}

.report-list-item {
  width: 100%;
  padding: 14px;
  text-align: left;
  border-radius: 18px;
  border: 1px solid var(--border-primary);
  background: var(--surface-card-bg-strong);
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.report-list-item:hover,
.report-list-item.active {
  transform: translateY(-1px);
  border-color: var(--color-primary);
  box-shadow: 0 12px 24px var(--bg-box-shadow);
}

.report-list-item-head {
  gap: 10px;
  color: var(--font-main-color);
}

.report-list-meta {
  margin-top: 8px;
  font-size: 12px;
  color: var(--font-tip-color);
}

.report-list-counters {
  margin-top: 10px;
  .flex-between;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--font-info-color);
}

.report-status-pill {
  padding: 4px 8px;
  border-radius: 20;
  background: var(--color-successBg);
  color: var(--color-success);
  font-size: 11px;
  font-weight: 600;
}

.report-content-panel {
  padding: 18px;
  gap: 16px;
  overflow: auto;
}

.report-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  border-radius: 22px;
  background: var(--surface-card-bg-hover);
}

.report-hero-date {
  font-size: 28px;
  font-weight: 700;
  color: var(--font-main-color);
}

.report-hero-subtitle {
  margin-top: 6px;
  max-width: 520px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--font-tip-color);
}

.report-hero-status {
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--color-successBg);
  font-size: 12px;
  font-weight: 600;
  color: var(--font-main-color);
}

.report-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.report-metric {
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  background: var(--surface-card-bg-strong);
  border: 1px solid var(--border-primary);
}

.report-metric-label {
  font-size: 11px;
  color: var(--font-tip-color);
}

.report-metric-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--font-main-color);
  word-break: break-word;
}

.report-markdown-panel {
  padding: 18px 20px;
  border-radius: 24px;
  background: var(--surface-card-bg);
  border: 1px solid var(--border-primary);
}

.report-detail-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 700;
  color: var(--font-main-color);
}

.report-markdown {
  font-size: 14px;
}

:deep(.report-drawer .ant-drawer-content) {
  background: var(--bg-content-color);
}

:deep(.report-drawer .ant-drawer-header) {
  padding: 18px 20px 10px;
  border-bottom: none;
}

:deep(.report-drawer .ant-drawer-body) {
  padding: 0 20px 20px;
}

@media (max-width: 960px) {
  .report-layout {
    grid-template-columns: 1fr;
  }

  .report-list-panel {
    max-height: 260px;
  }
}

@media (max-width: 640px) {
  .drawer-title-wrap,
  .report-hero {
    flex-direction: column;
  }

  .drawer-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .report-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
