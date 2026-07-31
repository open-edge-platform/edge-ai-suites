<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <template v-if="visibleRecords.length">
    <div class="activity-timeline-card section-card compact-card">
      <div class="timeline-header flex-between">
        <div class="timeline-header-left flex-left">
          <div class="timeline-title-row flex-left">
            <div class="section-title">
              {{ $t("smartHome.todayActivity") }}
            </div>
          </div>
        </div>
        <div class="timeline-header-right flex-left">
          <div class="timeline-title-tip">
            {{ $t("smartHome.timelineZoomTip") }}
          </div>
        </div>
      </div>
      <div
        ref="timelineScrollRef"
        class="timeline-scroll"
        :class="{ dragging: isTimelineDragging }"
        @wheel.prevent="handleTimelineWheel"
        @mousedown="handleTimelineDragStart"
        @scroll="handleTimelineScroll"
      >
        <div
          ref="timelineTrackRef"
          class="timeline-track"
          :style="{ width: `${timelineScale * 100}%` }"
        >
          <div class="timeline-segment recording"></div>
          <div
            v-if="timelineProgressPercent !== null"
            class="timeline-progress-line"
            :style="{ left: `${timelineProgressPercent}%` }"
          ></div>
          <a-tooltip
            v-for="entry in timelineEntries"
            :key="entry.id"
            placement="top"
          >
            <template #title>
              <div class="timeline-tooltip">
                <div class="timeline-tooltip-head">
                  {{ tooltipRecordForEntry(entry).title }}
                </div>
                <div class="timeline-tooltip-row">
                  <span>{{ $t("smartHome.tooltipStatus") }}</span>
                  <span>{{ tooltipRecordForEntry(entry).statusLabel }}</span>
                </div>
                <div class="timeline-tooltip-row">
                  <span>{{ $t("smartHome.tooltipTime") }}</span>
                  <span>{{ tooltipRecordForEntry(entry).timestampLabel }}</span>
                </div>
                <div
                  v-if="tooltipRecordForEntry(entry).recordKind === 'motion'"
                  class="timeline-tooltip-row"
                >
                  <span>{{ $t("smartHome.tooltipDuration") }}</span>
                  <span>{{
                    tooltipRecordForEntry(entry).durationSecondsLabel
                  }}</span>
                </div>
              </div>
            </template>
            <span
              class="timeline-segment motion"
              :class="[
                entry.recordKind,
                {
                  grouped: entry.isGrouped,
                  active: entry.records.some(
                    (record) => record.id === selectedRecordId,
                  ),
                },
              ]"
              :style="{
                left: `${getTimelinePosition(entry.startMinutes)}%`,
                width: `${getTimelineWidth(entry.widthMinutes)}%`,
                maxWidth: entry.isGrouped ? undefined : '8px',
              }"
              @click="handleTimelineEntryClick(entry)"
            ></span>
          </a-tooltip>
        </div>
        <div
          class="timeline-labels"
          :style="{ width: `${timelineScale * 100}%` }"
        >
          <span
            v-for="label in visibleTimelineLabels"
            :key="label.key"
            class="timeline-label"
            :style="{
              left: `${getTimelinePosition(label.minutes)}%`,
              transform:
                label.minutes === DAY_MINUTES
                  ? 'translateX(-100%)'
                  : 'translateX(-50%)',
            }"
          >
            {{ label.text }}
          </span>
        </div>
      </div>
      <div class="timeline-legend">
        <div class="legend-item flex-left">
          <div class="legend-dot mot"></div>
          <span>{{ $t("smartHome.timelineMotionEvent") }}</span>
        </div>
      </div>
    </div>

    <div class="history-section section-card">
      <div class="section-head">
        <div class="section-title">{{ $t("smartHome.recordTimeline") }}</div>
      </div>
      <div ref="historyListRef" class="history-list">
        <div
          v-for="record in orderedRecords"
          :key="record.id"
          :ref="setHistoryItemRef(record.id)"
          :data-record-id="record.id"
          class="history-item"
          :class="[
            record.recordKind,
            { active: selectedRecordId === record.id },
          ]"
        >
          <div class="history-marker"></div>
          <div class="history-time-block">
            <div class="history-time">{{ record.time }}</div>
            <div class="history-date">{{ record.date }}</div>
          </div>
          <div class="history-content">
            <div class="history-header flex-between">
              <div class="history-title-wrap flex-between">
                <div class="history-title">{{ record.title }}</div>
                <div class="history-meta flex-left">
                  <div class="history-status">
                    <span class="history-status-dot"></span>
                    <span>{{ record.statusLabel }}</span>
                  </div>
                  <div v-if="record.durationLabel" class="history-chip">
                    {{ record.durationLabel }}
                  </div>
                </div>
              </div>
            </div>
            <div
              v-if="record.description"
              class="history-desc-wrap intel-markdown flex-column"
            >
              <div
                :ref="setDescriptionRef(record.id)"
                class="history-desc"
                :class="{
                  collapsed:
                    hasDescriptionOverflow(record.id) &&
                    !isDescriptionExpanded(record.id),
                }"
                v-html="renderMarkdown(record.description)"
              ></div>
              <button
                v-if="hasDescriptionOverflow(record.id)"
                type="button"
                class="history-desc-toggle"
                @click="toggleDescription(record.id)"
              >
                {{
                  isDescriptionExpanded(record.id)
                    ? $t("smartHome.collapseDescription")
                    : $t("smartHome.expandDescription")
                }}
              </button>
            </div>
            <div class="history-preview-wrap">
              <VideoPlayer
                v-if="shouldLoadPreview(record.id)"
                :key="`preview-${record.id}`"
                class="history-player"
                width="100%"
                height="168px"
                :src="record.videoSrc"
                title=""
                muted
                :control="true"
                :control-btns="previewControlButtons"
              />
              <button
                v-else
                type="button"
                class="history-preview-placeholder"
                @click="loadPreview(record)"
              >
                <span
                  class="history-preview-placeholder-play"
                  aria-hidden="true"
                >
                  <span class="history-preview-placeholder-play-icon"></span>
                </span>
                <span class="history-preview-placeholder-badge">
                  {{
                    record.recordKind === "motion"
                      ? $t("smartHome.timelineMotionEvent")
                      : $t("smartHome.timelineStaticEvent")
                  }}
                </span>
                <span class="history-preview-placeholder-title">
                  {{ $t("smartHome.loadPreview") }}
                </span>
                <span class="history-preview-placeholder-subtitle">
                  {{ $t("smartHome.autoLoadPreviewHint") }}
                </span>
                <span class="history-preview-placeholder-time">
                  {{ record.time }}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </template>

  <div v-else class="history-empty-card vertical-center">
    <a-empty :description="$t('smartHome.noActivityRecords')" />
  </div>
</template>

<script setup lang="ts">
import dayjs from "dayjs";
import "highlight.js/styles/atom-one-dark.css";
import { marked } from "marked";
import type { ComponentPublicInstance } from "vue";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { videoPlay as VideoPlayer } from "vue3-video-play/dist/index.mjs";
import CustomRenderer from "@/utils/customRenderer";
import type { ActivityRecord, CameraTaskRecord } from "../type";
import { getSmartHomeSourceMeta } from "../deviceMeta";

interface TimelineEntry {
  id: string;
  startMinutes: number;
  widthMinutes: number;
  isGrouped: boolean;
  recordKind: ActivityRecord["recordKind"];
  records: ActivityRecord[];
}

interface TimelineLabel {
  key: string;
  minutes: number;
  text: string;
}

const TIMELINE_BUCKET_MINUTES = 5;
const TIMELINE_DETAIL_SCALE = 2;
const TIMELINE_MIN_SCALE = 1;
const DAY_MINUTES = 1440;
const MIN_VISIBLE_TIMELINE_MINUTES = 5;
const TIMELINE_MAX_SCALE = DAY_MINUTES / MIN_VISIBLE_TIMELINE_MINUTES;
const INITIAL_PREVIEW_LOAD_COUNT = 3;

const props = defineProps<{
  tasks: CameraTaskRecord[];
  selectedDate: string;
}>();

const emit = defineEmits<{
  select: [record: ActivityRecord];
}>();

const historyListRef = ref<HTMLElement | null>(null);
const historyItemElements = new Map<string, HTMLElement>();
const descriptionElements = new Map<string, HTMLElement>();
const expandedRecordIds = ref<string[]>([]);
const overflowRecordIds = ref<string[]>([]);
const timelineScrollRef = ref<HTMLElement | null>(null);
const timelineTrackRef = ref<HTMLElement | null>(null);
const timelineScale = ref(1);
const selectedRecordId = ref<string | null>(null);
const loadedPreviewRecordIds = ref<string[]>([]);
const visiblePreviewRecordIds = ref<string[]>([]);
const isTimelineDragging = ref(false);
const timelineDragStartX = ref(0);
const timelineDragStartScrollLeft = ref(0);
const timelineSuppressClick = ref(false);
const timelineScrollLeft = ref(0);
const timelineViewportWidth = ref(0);
const historyPreviewObserver = ref<IntersectionObserver | null>(null);
const { t } = useI18n();
const previewControlButtons = ["volume", "fullScreen"];

marked.setOptions({
  pedantic: false,
  gfm: true,
  breaks: false,
  renderer: CustomRenderer,
});

const buildRecordStatus = (status: string) => {
  if (!status) {
    return "";
  }

  return status === "completed" ? t("smartHome.recordStatusCompleted") : status;
};

const buildRecordTitle = (eventType: unknown) => {
  return eventType === "motion"
    ? t("smartHome.recordTypeUsage")
    : t("smartHome.recordTypeMonitoring");
};

const buildDurationLabel = (duration: number) => {
  if (duration <= 0) {
    return "";
  }

  const seconds =
    duration >= 10 ? Math.round(duration) : Number(duration.toFixed(1));

  return `${t("smartHome.recordDurationPrefix")} ${seconds} ${t("smartHome.recordDurationSeconds")}`;
};

const buildDurationSecondsLabel = (duration: number) => {
  return `${Math.max(0, Math.round(duration))}s`;
};

const mapTaskToRecord = (task: CameraTaskRecord): ActivityRecord => {
  const timestamp = dayjs(task.clip_start_time || task.created_at);
  const recordKind: ActivityRecord["recordKind"] =
    task.event_type === "motion" ? "motion" : "static";
  const videoSrc = `/api/tasks/${task.id}/clip?monitor_id=${encodeURIComponent(task.source_id)}`;

  return {
    id: `record-${task.id}`,
    time: timestamp.format("HH:mm:ss"),
    minutes: timestamp.hour() * 60 + timestamp.minute(),
    sortValue: timestamp.valueOf(),
    title: buildRecordTitle(task.event_type),
    camera: getSmartHomeSourceMeta(task.source_id, t).cameraLabel,
    description: task.summary_text,
    videoSrc,
    poster: "",
    date: timestamp.format("YYYY-MM-DD"),
    isoDate: timestamp.format("YYYY-MM-DD"),
    mediaType: "video",
    recordKind,
    statusLabel: buildRecordStatus(task.status),
    durationLabel: buildDurationLabel(task.clip_duration),
    durationSecondsLabel: buildDurationSecondsLabel(task.clip_duration),
    timestampLabel: timestamp.format("YYYY-MM-DD HH:mm:ss"),
    alertType: null,
    alertLabel: "",
  };
};

const visibleRecords = computed(() => {
  return props.tasks
    .filter((task) => task.event_type === "motion")
    .map(mapTaskToRecord)
    .filter((record) => record.isoDate === props.selectedDate)
    .sort((a, b) => a.sortValue - b.sortValue);
});

const timelineProgressPercent = computed(() => {
  if (props.selectedDate !== dayjs().format("YYYY-MM-DD")) {
    return null;
  }

  const now = dayjs();
  const minutes = now.hour() * 60 + now.minute() + now.second() / 60;

  return Math.min(100, Math.max(0, (minutes / DAY_MINUTES) * 100));
});

const getRecordStartMinutes = (record: ActivityRecord) => {
  const timestamp = dayjs(record.timestampLabel);
  return timestamp.hour() * 60 + timestamp.minute() + timestamp.second() / 60;
};

const getRecordDurationMinutes = (record: ActivityRecord) => {
  if (!record.durationLabel) {
    return 0;
  }

  const durationSeconds = Number.parseFloat(record.durationSecondsLabel);
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) {
    return 0;
  }

  return durationSeconds / 60;
};

const groupedTimelineEntries = computed<TimelineEntry[]>(() => {
  const bucketMap = new Map<number, ActivityRecord[]>();

  visibleRecords.value.forEach((record) => {
    const bucketStartMinutes =
      Math.floor(record.minutes / TIMELINE_BUCKET_MINUTES) *
      TIMELINE_BUCKET_MINUTES;
    const bucketRecords = bucketMap.get(bucketStartMinutes);

    if (bucketRecords) {
      bucketRecords.push(record);
      return;
    }

    bucketMap.set(bucketStartMinutes, [record]);
  });

  return [...bucketMap.entries()].map(([bucketStartMinutes, records]) => ({
    id: `timeline-bucket-${bucketStartMinutes}`,
    startMinutes: bucketStartMinutes,
    widthMinutes: TIMELINE_BUCKET_MINUTES,
    isGrouped: records.length > 1,
    recordKind: records.some((record) => record.recordKind === "motion")
      ? "motion"
      : "static",
    records,
  }));
});

const timelineEntries = computed<TimelineEntry[]>(() => {
  if (timelineScale.value >= TIMELINE_DETAIL_SCALE) {
    return visibleRecords.value.map((record) => ({
      id: `timeline-record-${record.id}`,
      startMinutes: getRecordStartMinutes(record),
      widthMinutes: Math.max(getRecordDurationMinutes(record), 0.6),
      isGrouped: false,
      recordKind: record.recordKind,
      records: [record],
    }));
  }

  return groupedTimelineEntries.value;
});

const timelineLabelInterval = computed(() => {
  if (timelineScale.value >= 8) {
    return 5;
  }

  if (timelineScale.value >= 5) {
    return 30;
  }

  if (timelineScale.value >= 2.5) {
    return 60;
  }

  return 180;
});

const formatTimelineLabel = (minutes: number) => {
  if (minutes === DAY_MINUTES) {
    return "24:00";
  }

  const hour = String(Math.floor(minutes / 60)).padStart(2, "0");
  const minute = String(minutes % 60).padStart(2, "0");
  return `${hour}:${minute}`;
};

const timelineLabels = computed<TimelineLabel[]>(() => {
  const interval = timelineLabelInterval.value;
  const labels: TimelineLabel[] = [];

  for (let minutes = 0; minutes < DAY_MINUTES; minutes += interval) {
    labels.push({
      key: `timeline-label-${minutes}`,
      minutes,
      text: formatTimelineLabel(minutes),
    });
  }

  labels.push({
    key: "timeline-label-1440",
    minutes: DAY_MINUTES,
    text: formatTimelineLabel(DAY_MINUTES),
  });

  return labels;
});

const visibleTimelineLabels = computed(() => {
  const scrollElement = timelineScrollRef.value;
  const trackElement = timelineTrackRef.value;

  if (!scrollElement || !trackElement) {
    return timelineLabels.value;
  }

  const contentWidth = Math.max(trackElement.scrollWidth, 1);
  const startMinutes = (timelineScrollLeft.value / contentWidth) * DAY_MINUTES;
  const viewportMinutes =
    ((timelineViewportWidth.value || scrollElement.clientWidth) /
      contentWidth) *
    DAY_MINUTES;
  const paddingMinutes =
    timelineLabelInterval.value <= MIN_VISIBLE_TIMELINE_MINUTES
      ? 0
      : timelineLabelInterval.value;
  const minMinutes = Math.max(0, startMinutes - paddingMinutes);
  const maxMinutes = Math.min(
    DAY_MINUTES,
    startMinutes + viewportMinutes + paddingMinutes,
  );

  return timelineLabels.value.filter(
    (label) => label.minutes >= minMinutes && label.minutes <= maxMinutes,
  );
});

const orderedRecords = computed(() => {
  return [...visibleRecords.value].reverse();
});

const initialPreviewRecordIds = computed(() => {
  return orderedRecords.value
    .slice(0, INITIAL_PREVIEW_LOAD_COUNT)
    .map((record) => record.id);
});

const renderMarkdown = (content?: string) => {
  return marked(content || "");
};

const setDescriptionRef = (recordId: string) => {
  return (element: Element | ComponentPublicInstance | null) => {
    if (element instanceof HTMLElement) {
      descriptionElements.set(recordId, element);
      return;
    }

    descriptionElements.delete(recordId);
  };
};

const setHistoryItemRef = (recordId: string) => {
  return (element: Element | ComponentPublicInstance | null) => {
    if (element instanceof HTMLElement) {
      historyItemElements.set(recordId, element);
      return;
    }

    historyItemElements.delete(recordId);
  };
};

const measureDescriptionOverflow = async () => {
  await nextTick();

  const nextOverflowIds: string[] = [];

  descriptionElements.forEach((element, recordId) => {
    const computedStyle = window.getComputedStyle(element);
    const lineHeight = Number.parseFloat(computedStyle.lineHeight || "0");
    const clampHeight = lineHeight > 0 ? lineHeight * 5 : 0;

    if (clampHeight > 0 && element.scrollHeight > clampHeight + 1) {
      nextOverflowIds.push(recordId);
    }
  });

  overflowRecordIds.value = nextOverflowIds;
  expandedRecordIds.value = expandedRecordIds.value.filter((recordId) =>
    nextOverflowIds.includes(recordId),
  );
};

const hasDescriptionOverflow = (recordId: string) => {
  return overflowRecordIds.value.includes(recordId);
};

const isDescriptionExpanded = (recordId: string) => {
  return expandedRecordIds.value.includes(recordId);
};

const toggleDescription = (recordId: string) => {
  if (isDescriptionExpanded(recordId)) {
    expandedRecordIds.value = expandedRecordIds.value.filter(
      (id) => id !== recordId,
    );
    return;
  }

  expandedRecordIds.value = [...expandedRecordIds.value, recordId];
};

const clamp = (value: number, min: number, max: number) => {
  return Math.min(max, Math.max(min, value));
};

const tooltipRecordForEntry = (entry: TimelineEntry) => {
  return entry.records[entry.records.length - 1] || entry.records[0];
};

const syncTimelineViewportState = () => {
  const scrollElement = timelineScrollRef.value;

  if (!scrollElement) {
    return;
  }

  timelineScrollLeft.value = scrollElement.scrollLeft;
  timelineViewportWidth.value = scrollElement.clientWidth;
};

const getTimelineZoomFactor = (currentScale: number) => {
  const logBoost = Math.log10(currentScale + 1);
  return 1.35 + Math.min(logBoost * 0.55, 1.65);
};

const scrollToHistoryRecord = async (recordId: string) => {
  await nextTick();

  const historyItem = historyItemElements.get(recordId);
  if (!historyItem) {
    return;
  }

  historyItem.scrollIntoView({ behavior: "smooth", block: "center" });
};

const shouldLoadPreview = (recordId: string) => {
  return (
    loadedPreviewRecordIds.value.includes(recordId) ||
    visiblePreviewRecordIds.value.includes(recordId) ||
    initialPreviewRecordIds.value.includes(recordId) ||
    selectedRecordId.value === recordId
  );
};

const rememberLoadedPreview = (recordId: string) => {
  if (shouldLoadPreview(recordId)) {
    return;
  }

  loadedPreviewRecordIds.value = [
    ...loadedPreviewRecordIds.value,
    recordId,
  ].slice(-6);
};

const loadPreview = (record: ActivityRecord) => {
  rememberLoadedPreview(record.id);
  playRecord(record);
};

const syncVisiblePreviewRecordIds = (entries: IntersectionObserverEntry[]) => {
  const nextVisibleRecordIds = new Set(visiblePreviewRecordIds.value);

  entries.forEach((entry) => {
    const element = entry.target as HTMLElement;
    const recordId = element.dataset.recordId;

    if (!recordId) {
      return;
    }

    if (entry.isIntersecting) {
      nextVisibleRecordIds.add(recordId);
      return;
    }

    nextVisibleRecordIds.delete(recordId);
  });

  visiblePreviewRecordIds.value = [...nextVisibleRecordIds];
};

const observeHistoryItems = async () => {
  await nextTick();

  const observer = historyPreviewObserver.value;
  if (!observer) {
    return;
  }

  observer.disconnect();
  historyItemElements.forEach((element) => {
    observer.observe(element);
  });
};

const handleTimelineEntryClick = (entry: TimelineEntry) => {
  if (timelineSuppressClick.value) {
    timelineSuppressClick.value = false;
    return;
  }

  const targetRecord =
    entry.records[entry.records.length - 1] || entry.records[0];

  if (!targetRecord) {
    return;
  }

  selectedRecordId.value = targetRecord.id;
  rememberLoadedPreview(targetRecord.id);
  emit("select", targetRecord);
  void scrollToHistoryRecord(targetRecord.id);
};

const handleTimelineWheel = async (event: WheelEvent) => {
  const scrollElement = timelineScrollRef.value;
  const trackElement = timelineTrackRef.value;

  if (!scrollElement || !trackElement) {
    return;
  }

  const zoomFactor = getTimelineZoomFactor(timelineScale.value);
  const nextScale = clamp(
    Number(
      (event.deltaY < 0
        ? timelineScale.value * zoomFactor
        : timelineScale.value / zoomFactor
      ).toFixed(4),
    ),
    TIMELINE_MIN_SCALE,
    TIMELINE_MAX_SCALE,
  );

  if (nextScale === timelineScale.value) {
    return;
  }

  const rect = scrollElement.getBoundingClientRect();
  const pointerOffset = event.clientX - rect.left;
  const contentOffset = scrollElement.scrollLeft + pointerOffset;
  const previousWidth = trackElement.scrollWidth;
  const offsetRatio = contentOffset / Math.max(previousWidth, 1);

  timelineScale.value = nextScale;
  await nextTick();

  const nextWidth = timelineTrackRef.value?.scrollWidth || previousWidth;
  scrollElement.scrollLeft = Math.max(
    0,
    offsetRatio * nextWidth - pointerOffset,
  );
  syncTimelineViewportState();
};

const handleTimelineScroll = () => {
  syncTimelineViewportState();
};

const handleTimelineDragMove = (event: MouseEvent) => {
  const scrollElement = timelineScrollRef.value;

  if (!isTimelineDragging.value || !scrollElement) {
    return;
  }

  const deltaX = event.clientX - timelineDragStartX.value;
  if (Math.abs(deltaX) > 4) {
    timelineSuppressClick.value = true;
  }

  scrollElement.scrollLeft = timelineDragStartScrollLeft.value - deltaX;
};

const handleTimelineDragEnd = () => {
  if (!isTimelineDragging.value) {
    return;
  }

  isTimelineDragging.value = false;

  window.setTimeout(() => {
    timelineSuppressClick.value = false;
  }, 0);
};

const handleTimelineDragStart = (event: MouseEvent) => {
  const scrollElement = timelineScrollRef.value;

  if (!scrollElement || event.button !== 0 || timelineScale.value <= 1) {
    return;
  }

  isTimelineDragging.value = true;
  timelineDragStartX.value = event.clientX;
  timelineDragStartScrollLeft.value = scrollElement.scrollLeft;
  timelineSuppressClick.value = false;
};

const scrollToLatestRecord = async () => {
  await nextTick();

  const historyList = historyListRef.value;

  if (!historyList) {
    return;
  }

  historyList.scrollTop = 0;
};

watch(
  visibleRecords,
  (records) => {
    if (!records.some((record) => record.id === selectedRecordId.value)) {
      selectedRecordId.value = null;
    }

    loadedPreviewRecordIds.value = loadedPreviewRecordIds.value.filter(
      (recordId) => records.some((record) => record.id === recordId),
    );
    visiblePreviewRecordIds.value = visiblePreviewRecordIds.value.filter(
      (recordId) => records.some((record) => record.id === recordId),
    );

    void scrollToLatestRecord();
    void measureDescriptionOverflow();
    void observeHistoryItems();
  },
  { immediate: true },
);

const handleWindowResize = () => {
  syncTimelineViewportState();
  void measureDescriptionOverflow();
};

onMounted(() => {
  historyPreviewObserver.value = new IntersectionObserver(
    (entries) => {
      syncVisiblePreviewRecordIds(entries);
    },
    {
      root: historyListRef.value,
      rootMargin: "180px 0px 220px 0px",
      threshold: 0.12,
    },
  );

  syncTimelineViewportState();
  void observeHistoryItems();
  window.addEventListener("resize", handleWindowResize);
  window.addEventListener("mousemove", handleTimelineDragMove);
  window.addEventListener("mouseup", handleTimelineDragEnd);
});

onUnmounted(() => {
  historyPreviewObserver.value?.disconnect();
  window.removeEventListener("resize", handleWindowResize);
  window.removeEventListener("mousemove", handleTimelineDragMove);
  window.removeEventListener("mouseup", handleTimelineDragEnd);
});

const getTimelinePosition = (minutes: number) => {
  return Math.min(100, Math.max(0, (minutes / DAY_MINUTES) * 100));
};

const getTimelineWidth = (minutes: number) => {
  return Math.min(100, Math.max((minutes / DAY_MINUTES) * 100, 0.35));
};

const playRecord = (record: ActivityRecord) => {
  selectedRecordId.value = record.id;
  emit("select", record);
};
</script>

<style scoped lang="less">
.section-card {
  border-radius: 22px;
  background: var(--surface-panel-bg);
  border: 1px solid var(--border-primary);
  padding: 12px 16px;
  box-shadow: 0 10px 24px var(--bg-box-shadow);
}

.compact-card {
  padding-top: 10px;
  padding-bottom: 10px;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--font-main-color);
}

.timeline-header {
  gap: 12px;
  flex-wrap: wrap;
}

.timeline-title-row {
  gap: 8px;
  flex-wrap: wrap;
}

.timeline-title-tip {
  font-size: 11px;
  color: var(--font-tip-color);
  white-space: nowrap;
}

.timeline-cam-sub {
  margin-top: 4px;
  font-size: 11px;
  color: var(--font-tip-color);
}

.timeline-cam-divider {
  margin: 0 6px;
}

.timeline-date-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--color-primaryBg);
  border: 1px solid var(--border-primary);
  font-size: 11px;
  color: var(--font-main-color);
  line-height: 1;
}

.timeline-scroll {
  margin-top: 8px;
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: 4px;
  scrollbar-width: none;
  cursor: grab;
  -ms-overflow-style: none;
}

.timeline-scroll.dragging {
  cursor: grabbing;
  user-select: none;
}

.timeline-scroll::-webkit-scrollbar {
  width: 0;
  height: 0;
}

.timeline-track {
  position: relative;
  height: 28px;
  min-width: 100%;
  overflow: visible;
}

.timeline-segment {
  position: absolute;
  cursor: pointer;
  transition:
    opacity 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.timeline-segment:hover {
  opacity: 1;
}

.timeline-segment.recording {
  top: 4px;
  left: 0;
  width: 100%;
  height: 20px;
  border-radius: 6px;
  background: var(--color-primaryBg);
  border: 1px solid var(--border-primary);
  cursor: default;
}

.timeline-segment.motion {
  top: 6px;
  min-width: 6px;
  height: 16px;
  padding: 0;
  transform-origin: center center;
  border: 1px solid var(--timeline-motion-color, var(--color-primary));
  border-radius: 5px;
  background: var(--timeline-motion-color, var(--color-primary));
  opacity: 0.72;
  box-shadow: 0 0 0 2px var(--timeline-motion-ring, var(--border-primary));
}

.timeline-segment.motion::before {
  content: "";
  position: absolute;
  top: -6px;
  right: -4px;
  bottom: -6px;
  left: -4px;
}

.timeline-segment.motion.static {
  background: var(--timeline-static-color, var(--color-warning));
  border-color: var(--timeline-static-color, var(--color-warning));
  box-shadow: 0 0 0 2px var(--timeline-static-ring, var(--border-warning));
}

.timeline-segment.motion.grouped {
  min-width: 8px;
}

.timeline-segment.motion:hover {
  z-index: 5;
  transform: translateY(-3px) scale(1.2);
  opacity: 1;
  box-shadow:
    0 0 0 3px var(--timeline-motion-ring, var(--border-primary)),
    0 12px 22px var(--bg-box-shadow);
}

.timeline-segment.motion.static:hover {
  box-shadow:
    0 0 0 3px var(--timeline-static-ring, var(--border-warning)),
    0 12px 22px var(--bg-box-shadow);
}

.timeline-segment.motion.active {
  z-index: 3;
  background: var(--timeline-motion-color, var(--color-primary));
  border-color: var(--timeline-motion-color, var(--color-primary));
  opacity: 1;
  box-shadow:
    0 0 0 3px var(--timeline-motion-ring, var(--border-primary)),
    0 10px 18px var(--bg-box-shadow);
}

.timeline-segment.motion.static.active {
  background: var(--timeline-static-color, var(--color-warning));
  border-color: var(--timeline-static-color, var(--color-warning));
  opacity: 1;
  box-shadow:
    0 0 0 3px var(--timeline-static-ring, var(--border-warning)),
    0 10px 18px var(--bg-box-shadow);
}

.timeline-progress-line {
  position: absolute;
  top: 0;
  height: 28px;
  width: 2px;
  background: color-mix(
    in srgb,
    var(--color-warning) 82%,
    var(--border-warning)
  );
  z-index: 4;
  pointer-events: none;
}

.timeline-progress-line::after {
  content: "";
  position: absolute;
  top: -3px;
  left: -3px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: color-mix(
    in srgb,
    var(--color-warning) 82%,
    var(--border-warning)
  );
}

.timeline-labels {
  position: relative;
  height: 16px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--font-tip-color);
  min-width: 100%;
}

.timeline-label {
  position: absolute;
  top: 0;
  white-space: nowrap;
  line-height: 16px;
}

.timeline-legend {
  display: flex;
  gap: 14px;
  margin-top: 6px;
  font-size: 11px;
  color: var(--font-tip-color);
  flex-wrap: wrap;
}

.legend-item {
  display: inline-flex;
  gap: 6px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.legend-dot.mot {
  background: var(--timeline-motion-color, var(--color-primary));
  border: 1px solid var(--timeline-motion-color, var(--color-primary));
}

.legend-dot.sta {
  background: var(--timeline-static-color, var(--color-warning));
  border: 1px solid var(--timeline-static-color, var(--color-warning));
}

.timeline-tooltip {
  .flex-column;
  gap: 4px;
  min-width: 160px;
}

.timeline-tooltip-head {
  font-size: 12px;
  font-weight: 600;
}

.timeline-tooltip-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
}

.history-preview-placeholder {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  height: 168px;
  border: none;
  border-radius: 16px;
  background:
    radial-gradient(
      circle at top right,
      var(--color-primaryBg),
      transparent 34%
    ),
    linear-gradient(
      135deg,
      var(--surface-card-bg),
      var(--surface-card-bg-strong)
    );
  box-shadow: inset 0 0 0 1px var(--border-primary);
  color: var(--font-main-color);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 20px var(--bg-box-shadow);
    background:
      radial-gradient(
        circle at top right,
        var(--color-primaryBg),
        transparent 36%
      ),
      linear-gradient(
        135deg,
        var(--surface-card-bg-hover),
        var(--surface-card-bg)
      );
  }
}

.history-preview-placeholder-play {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--surface-panel-bg) 78%, transparent);
  box-shadow:
    0 10px 24px var(--bg-box-shadow),
    inset 0 0 0 1px var(--border-primary);
}

.history-preview-placeholder-play-icon {
  width: 0;
  height: 0;
  margin-left: 3px;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-left: 12px solid var(--color-primary);
}

.history-preview-placeholder-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--surface-panel-bg);
  border: 1px solid var(--border-primary);
  font-size: 11px;
  font-weight: 600;
  color: var(--font-tip-color);
}

.history-preview-placeholder-title {
  font-size: 13px;
  font-weight: 600;
}

.history-preview-placeholder-subtitle {
  font-size: 11px;
  color: var(--font-tip-color);
}

.history-preview-placeholder-time {
  font-size: 11px;
  color: var(--font-tip-color);
}

.history-section {
  flex: 1;
  min-height: 0;
  .flex-column;
}

.history-empty-card {
  margin: auto;
}

.history-list {
  margin-top: 14px;
  flex: 1;
  overflow-y: auto;
  padding-right: 0;
  .flex-column;
  gap: 16px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.history-list::-webkit-scrollbar {
  width: 0;
  height: 0;
}

.history-item {
  position: relative;
  display: grid;
  grid-template-columns: 14px 88px minmax(0, 1fr);
  gap: 14px;
  padding: 8px 0 0;
}

.history-marker {
  position: relative;
  width: 14px;
}

.history-marker::before {
  content: "";
  position: absolute;
  top: 8px;
  left: 2px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-primary);
  box-shadow: 0 0 0 4px var(--border-primary);
}

.history-item::after {
  content: "";
  position: absolute;
  left: 6px;
  top: 30px;
  bottom: -16px;
  width: 2px;
  background: var(--border-primary);
}

.history-item:last-child::after {
  display: none;
}

.history-item.active .history-marker::before {
  background: var(--color-success);
}

.history-item.static .history-marker::before {
  background: var(--color-warning);
  box-shadow: 0 0 0 4px var(--border-warning);
}

.history-item.motion .history-marker::before {
  background: var(--color-primary);
  box-shadow: 0 0 0 4px var(--border-primary);
}

.history-item.static.active .history-marker::before {
  background: color-mix(
    in srgb,
    var(--color-warning) 88%,
    var(--border-warning)
  );
}

.history-time-block {
  padding-top: 2px;
}

.history-time {
  font-size: 18px;
  font-weight: 700;
  color: var(--font-main-color);
}

.history-date {
  margin-top: 4px;
  font-size: 11px;
  color: var(--font-tip-color);
}

.history-content {
  padding: 16px 16px 14px;
  border-radius: 22px;
  background: var(--surface-card-bg);
  border: 1px solid var(--border-primary);
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.history-item:hover .history-content,
.history-item.active .history-content {
  transform: translateY(-1px);
  border-color: var(--color-primary);
  box-shadow: 0 14px 28px var(--bg-box-shadow);
}

.history-item.static:hover .history-content,
.history-item.static.active .history-content {
  border-color: color-mix(
    in srgb,
    var(--color-warning) 78%,
    var(--border-warning) 22%
  );
}

.history-item.motion:hover .history-content,
.history-item.motion.active .history-content {
  border-color: var(--color-primary);
}

.history-header {
  width: 100%;
  gap: 12px;
}

.history-title-wrap {
  width: 100%;
  min-width: 0;
  gap: 10px;
}

.history-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--font-main-color);
}

.history-meta {
  gap: 10px;
  flex-wrap: wrap;
}

.history-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--color-successBg);
  color: var(--font-main-color);
  font-size: 11px;
  font-weight: 600;
}

.history-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
  flex: none;
}

.history-chip {
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--color-warningBg);
  color: var(--color-warning);
  font-size: 11px;
  font-weight: 600;
}

.history-item.static .history-content {
  border-left: 3px solid
    color-mix(in srgb, var(--color-warning) 88%, var(--border-warning));
}

.history-item.motion .history-content {
  border-left: 3px solid var(--color-primary);
}

.history-desc-wrap {
  align-items: stretch;
  margin-top: 8px;
}

.history-desc {
  font-size: 12px;
  line-height: 1.65;
  color: var(--font-info-color);
  word-break: break-word;

  &.collapsed {
    display: -webkit-box;
    overflow: hidden;
    line-clamp: 5;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 5;
  }
}

.history-desc-toggle {
  align-self: flex-end;
  margin-top: 6px;
  border: none;
  background: transparent;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary);
  cursor: pointer;

  &:hover {
    color: var(--color-primary-hover);
  }
}

.history-desc :deep(p),
.history-desc :deep(ul),
.history-desc :deep(ol),
.history-desc :deep(pre),
.history-desc :deep(blockquote) {
  margin: 0 0 8px;
}

.history-desc :deep(p:last-child),
.history-desc :deep(ul:last-child),
.history-desc :deep(ol:last-child),
.history-desc :deep(pre:last-child),
.history-desc :deep(blockquote:last-child) {
  margin-bottom: 0;
}

.history-desc :deep(ul),
.history-desc :deep(ol) {
  padding-left: 18px;
}

.history-desc :deep(a) {
  color: var(--color-primary);
}

.history-desc :deep(code) {
  padding: 1px 4px;
  border-radius: 6px;
  background: var(--color-primaryBg);
  color: var(--font-main-color);
}

.history-desc :deep(pre) {
  overflow: auto;
  border-radius: 12px;
}

.history-preview-wrap {
  margin-top: 12px;
  max-width: 320px;
  overflow: hidden;
  border-radius: 16px;
  box-shadow: 0 14px 26px var(--bg-box-shadow);
  background: var(--media-stage-bg);
  border: 1px solid var(--border-primary);
}

:deep(.history-player) {
  width: 100%;
  height: 168px;
}

@media (max-width: 1440px) {
  .history-item {
    grid-template-columns: 14px 72px minmax(0, 1fr);
  }
}

@media (max-width: 768px) {
  .timeline-title-tip {
    white-space: normal;
  }

  .timeline-header-right {
    width: 100%;
  }

  .timeline-date-chip {
    width: 100%;
    text-align: left;
  }

  .history-item {
    grid-template-columns: 14px 1fr;
  }

  .history-time-block,
  .history-content {
    grid-column: 2;
  }

  .history-content,
  .history-preview-wrap {
    max-width: 100%;
  }
}
</style>
