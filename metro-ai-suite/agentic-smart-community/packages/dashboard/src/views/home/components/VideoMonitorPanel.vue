<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="monitor-panel">
    <div class="panel-header flex-between">
      <div class="panel-title">{{ $t("smartCommunity.cameraMonitorTitle") }}</div>
      <div class="panel-controls flex-left">
        <div class="date-switcher flex-left">
          <a-date-picker
            :value="selectedDate"
            :allow-clear="false"
            size="small"
            format="YYYY-MM-DD"
            :disabled-date="disableDate"
            @change="handleDateChange"
          />
        </div>
        <a-button
          class="report-btn"
          size="small"
          :loading="reportLoading"
          @click="handleOpenReport"
        >
          <template #icon>
            <FileTextOutlined />
          </template>
          {{ $t("smartCommunity.viewReport") }}
        </a-button>
        <a-button
          v-if="hasReports"
          class="export-btn"
          size="small"
          @click="handleExportReport()"
        >
          <template #icon>
            <DownloadOutlined />
          </template>
          {{ $t("smartCommunity.exportReport") }}
        </a-button>
      </div>
    </div>
    <div class="video-stage-shell">
      <div class="video-stage">
        <video
          v-if="recordingSession"
          ref="recordingVideoRef"
          :key="recordingSession.segment.id"
          class="main-player live-player"
          :src="recordingStreamUrl"
          autoplay
          playsinline
          controls
          preload="auto"
          @loadedmetadata="handleRecordingLoaded"
          @timeupdate="handleRecordingTimeUpdate"
          @ended="handleRecordingEnded"
          @error="handleRecordingError"
        ></video>
        <video
          v-else-if="isLiveMode && activeRecord.videoSrc"
          ref="liveVideoRef"
          :key="activeRecord.videoSrc"
          class="main-player live-player"
          autoplay
          muted
          playsinline
          controls
          preload="auto"
        >
        </video>
        <video
          v-else-if="activeRecord.videoSrc && isLiveMode"
          :key="`main-${activeRecord.id}-live`"
          :src="activeRecord.videoSrc"
          controls
          autoplay
          muted
          class="w-full h-full object-contain bg-black"
        ></video
        ><VideoPlayer
          v-else-if="activeRecord.videoSrc && !isLiveMode"
          :key="`main-${activeRecord.id}-${isLiveMode ? 'live' : 'history'}`"
          class="main-player"
          width="100%"
          height="240px"
          :src="activeRecord.videoSrc"
          title=""
          :autoPlay="true"
          :muted="false"
          :loop="false"
          :control="true"
          :control-btns="mainControlButtons"
        />
        <div v-else class="main-empty-state vertical-center">
          {{ $t("smartCommunity.reportNoContent") }}
        </div>

        <div class="video-topbar flex-between">
          <div class="video-mode-tag" :class="{ live: isLiveMode }">
            {{ videoModeLabel }}
          </div>
          <div class="video-topbar-actions flex-end">
            <div class="realtime-pill flex-left">
              <span class="realtime-pill-value">{{ realtimeEventValue }}</span>
            </div>
            <a-button
              v-if="!isLiveMode"
              type="primary"
              size="small"
              class="back-live-btn"
              @click="switchToLive"
            >
              <template #icon>
                <RollbackOutlined />
              </template>
              {{ $t("smartCommunity.backToNow") }}
            </a-button>
          </div>
        </div>

        <div class="video-content">
          <div class="video-kicker">{{ activeRecord.camera }}</div>
          <div class="video-title">{{ activeRecord.title }}</div>
          <div class="video-time">
            {{ videoTimeLabel }}
          </div>
        </div>
      </div>
    </div>

    <ActivityFeed
      :loading="activityLoading"
      :tasks="taskList"
      :recordings="recordingList"
      :playback-time-ms="playbackTimeMs"
      :selected-date="selectedDateLabel"
      :selected-source-id="selectedSourceId"
      @select="handleHistoryRecordSelect"
      @seek-recording="handleSeekRecording"
    />

    <ReportDrawer
      v-if="reportDrawerVisible"
      :selected-date="selectedDateLabel"
      :drawer-data="reportList"
      @close="reportDrawerVisible = false"
      @export="handleExportReport"
    />
  </div>
</template>

<script setup lang="ts">
import {
  DownloadOutlined,
  FileTextOutlined,
  RollbackOutlined,
} from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import dayjs, { type Dayjs } from "dayjs";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { videoPlay as VideoPlayer } from "vue3-video-play/dist/index.mjs";
import ActivityFeed from "./ActivityFeed.vue";
import ReportDrawer from "./ReportDrawer.vue";
import type {
  CameraReport,
  ActivityRecord,
  CameraTaskRecord,
  RecordingSegment,
} from "../type";
import "vue3-video-play/dist/style.css";
import {
  buildRecordingStreamUrl,
  getCameraActivityList,
  getCameraRecordings,
  getCamReport,
} from "@/api/smartCommunity";
import { getSmartCommunitySourceMeta } from "../deviceMeta";
import { findNextRecording, findRecordingAt } from "../recordings";

const props = defineProps<{
  selectedDate: Dayjs;
}>();

const emit = defineEmits<{
  (event: "update:selectedDate", value: Dayjs): void;
}>();

const { t } = useI18n();
const route = useRoute();

const MAX_STREAM_QUEUE_BYTES = 8 * 1024 * 1024;
const MAX_STREAM_BUFFER_SECONDS = 30;
const RETAIN_STREAM_BUFFER_SECONDS = 20;
const LIVE_EDGE_TOLERANCE_SECONDS = 3;
const LIVE_WATCHDOG_INTERVAL_MS = 1000;
const LIVE_RECONNECT_MIN_DELAY_MS = 1000;
const LIVE_RECONNECT_MAX_DELAY_MS = 15000;

const mainControlButtons = [
  "speedRate",
  "volume",
  "setting",
  "pageFullScreen",
  "fullScreen",
];

const taskList = ref<CameraTaskRecord[]>([]);
const reportList = ref<CameraReport[]>([]);
const reportDrawerVisible = ref(false);
const isLiveMode = ref(true);
const activityLoading = ref(false);
const reportLoading = ref(false);
const liveNow = ref(dayjs());
const liveVideoRef = ref<HTMLVideoElement | null>(null);
const recordingList = ref<RecordingSegment[]>([]);
const recordingVideoRef = ref<HTMLVideoElement | null>(null);
const recordingSession = ref<{
  segment: RecordingSegment;
  offsetSeconds: number;
} | null>(null);
const recordingElapsedSeconds = ref(0);

const selectedDate = computed({
  get: () => props.selectedDate,
  set: (value: Dayjs) => emit("update:selectedDate", value),
});

const selectedSourceId = computed(() => {
  const sourceId = route.query.source_id;
  return typeof sourceId === "string" ? sourceId : "";
});

const currentSourceMeta = computed(() => {
  return getSmartCommunitySourceMeta(selectedSourceId.value, t);
});

const liveVideoSrc = computed(() => {
  if (!selectedSourceId.value) {
    return "";
  }

  return `/api/monitors/${encodeURIComponent(selectedSourceId.value)}/live-stream`;
});

const currentCameraLabel = computed(() => {
  return currentSourceMeta.value.cameraLabel;
});

const buildFallbackActiveRecord = (
  targetDate: Dayjs = selectedDate.value,
): ActivityRecord => ({
  id: "live",
  time: dayjs().format("HH:mm:ss"),
  minutes: 0,
  sortValue: dayjs().valueOf(),
  title: currentSourceMeta.value.liveTitle,
  camera: currentCameraLabel.value,
  description: currentSourceMeta.value.liveDescription,
  videoSrc: liveVideoSrc.value,
  poster: "",
  date: targetDate.format("YYYY-MM-DD"),
  isoDate: targetDate.format("YYYY-MM-DD"),
  mediaType: "video",
  recordKind: "static",
  statusLabel: t("smartCommunity.realtimeStatus"),
  durationLabel: "",
  durationSecondsLabel: "0s",
  timestampLabel: `${targetDate.format("YYYY-MM-DD")} ${dayjs().format("HH:mm:ss")}`,
  alertType: null,
  alertLabel: "",
});

const activeRecord = ref<ActivityRecord>(buildFallbackActiveRecord());

const selectedDateLabel = computed(() => {
  return selectedDate.value.format("YYYY-MM-DD");
});

const hasReports = computed(() => reportList.value.length > 0);

const recordingStreamUrl = computed(() => {
  const session = recordingSession.value;
  if (!session || !selectedSourceId.value) {
    return "";
  }

  return buildRecordingStreamUrl(session.segment.id, selectedSourceId.value);
});

// Wall-clock instant currently on screen during playback — drives both the
// header pill and the timeline's playback marker.
const playbackTimeMs = computed(() => {
  const session = recordingSession.value;
  if (!session) {
    return null;
  }

  return session.segment.startMs + recordingElapsedSeconds.value * 1000;
});

const videoModeLabel = computed(() => {
  if (recordingSession.value) {
    return t("smartCommunity.recordingPlayback");
  }

  return isLiveMode.value
    ? t("smartCommunity.liveVideo")
    : t("smartCommunity.historyVideo");
});

const realtimeEventValue = computed(() => {
  if (playbackTimeMs.value !== null) {
    return dayjs(playbackTimeMs.value).format("YYYY-MM-DD HH:mm:ss");
  }

  return isLiveMode.value
    ? `${selectedDateLabel.value} ${liveNow.value.format("HH:mm:ss")}`
    : `${activeRecord.value.date} ${activeRecord.value.time}`;
});

const videoTimeLabel = computed(() => {
  if (playbackTimeMs.value !== null) {
    return dayjs(playbackTimeMs.value).format("HH:mm:ss");
  }

  return isLiveMode.value
    ? t("smartCommunity.liveNow")
    : activeRecord.value.time;
});

let activityPollingTimer: number | null = null;
let reportPollingTimer: number | null = null;
let liveClockTimer: number | null = null;
let latestActivityRequestId = 0;
let latestReportRequestId = 0;
let latestRecordingRequestId = 0;
let cleanupLiveStream: (() => void) | null = null;
let liveReconnectTimer: number | null = null;
let liveReconnectDelay = LIVE_RECONNECT_MIN_DELAY_MS;
let recordingErrorStreak = 0;

const buildRecordStatus = (status: string) => {
  if (!status) {
    return "";
  }

  return status === "completed" ? t("smartCommunity.recordStatusCompleted") : status;
};

const buildReportExportContent = (reports: CameraReport[]) => {
  const exportTimestamp = dayjs().format("YYYY-MM-DD HH:mm:ss");
  const lines = [
    `# ${t("smartCommunity.reportExportTitle")}`,
    "",
    `${t("smartCommunity.reportGeneratedAt")}: ${exportTimestamp}`,
    `${t("smartCommunity.reportSelectedDate")}: ${selectedDateLabel.value}`,
    `${t("smartCommunity.reportCountLabel")}: ${reports.length}`,
    "",
  ];

  reports.forEach((report, index) => {
    lines.push(`## ${index + 1}. ${report.report_date}`);
    lines.push(`${t("smartCommunity.reportCreatedAtLabel")}: ${report.created_at}`);
    lines.push(
      `${t("smartCommunity.reportStatusLabel")}: ${buildRecordStatus(report.status)}`,
    );
    lines.push(`${t("smartCommunity.reportEventCount")}: ${report.event_count}`);
    lines.push(`${t("smartCommunity.reportMotionCount")}: ${report.motion_count}`);
    lines.push(`${t("smartCommunity.reportPromptTokens")}: ${report.prompt_tokens}`);
    lines.push("");
    lines.push(`### ${t("smartCommunity.reportDetailSection")}`);
    lines.push(report.report_text?.trim() || "");
    lines.push("");
  });

  return lines.join("\n");
};

const queryCamFridgeList = async ({ showLoading = false } = {}) => {
  const requestId = ++latestActivityRequestId;

  if (!selectedSourceId.value) {
    taskList.value = [];
    activityLoading.value = false;
    return;
  }

  if (showLoading) {
    activityLoading.value = true;
    taskList.value = [];
  }

  try {
    const params = {
      date: selectedDate.value.format("YYYY-MM-DD"),
      source_id: selectedSourceId.value,
    };
    const res = await getCameraActivityList(params);

    if (requestId !== latestActivityRequestId) {
      return;
    }

    taskList.value = res.tasks || [];
  } catch {
    if (requestId !== latestActivityRequestId) {
      return;
    }

    if (showLoading) {
      taskList.value = [];
    }
  } finally {
    if (requestId === latestActivityRequestId) {
      activityLoading.value = false;
    }
  }
};

const queryRecordings = async () => {
  const requestId = ++latestRecordingRequestId;

  if (!selectedSourceId.value) {
    recordingList.value = [];
    return;
  }

  try {
    const res = await getCameraRecordings({
      date: selectedDate.value.format("YYYY-MM-DD"),
      source_id: selectedSourceId.value,
    });

    if (requestId !== latestRecordingRequestId) {
      return;
    }

    recordingList.value = res.recordings || [];
  } catch {
    if (requestId === latestRecordingRequestId) {
      recordingList.value = [];
    }
  }
};

const queryCamReport = async (silent = true) => {
  const requestId = ++latestReportRequestId;

  if (!selectedSourceId.value) {
    reportList.value = [];
    reportLoading.value = false;
    return;
  }

  reportLoading.value = true;
  try {
    const params = {
      date: selectedDate.value.format("YYYY-MM-DD"),
      source_id: selectedSourceId.value,
    };
    const res = await getCamReport(params);

    if (requestId !== latestReportRequestId) {
      return;
    }

    reportList.value = res.reports || [];
  } catch (error) {
    if (requestId !== latestReportRequestId) {
      return;
    }

    console.error("Report API Error:", error);
    reportList.value = [];

    if (!silent) {
      message.error(t("smartCommunity.reportLoadFailed"));
    }
  } finally {
    if (requestId === latestReportRequestId) {
      reportLoading.value = false;
    }
  }
};

const resetReportData = () => {
  reportList.value = [];
};

const disableDate = (current: Dayjs) => {
  const today = dayjs().endOf("day");
  const thirtyDaysAgo = dayjs().subtract(29, "day").startOf("day");
  return current.isAfter(today) || current.isBefore(thirtyDaysAgo);
};

const handleDateChange = (value: Dayjs | null) => {
  selectedDate.value = value ?? dayjs();
  clearRecordingSession();
  activeRecord.value = buildFallbackActiveRecord(selectedDate.value);
  isLiveMode.value = true;
  resetReportData();
  void queryCamFridgeList({ showLoading: true });
  void queryRecordings();
  void queryCamReport();
};

const downloadReportFile = (content: string, reportDate: string) => {
  const blob = new Blob([content], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `${selectedSourceId.value}-report-${reportDate}.md`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

const handleOpenReport = async () => {
  // Re-check in case a report was generated since the last load.
  if (!hasReports.value) {
    await queryCamReport(false);
  }
  if (!hasReports.value) {
    message.info(t("smartCommunity.reportEmptyHint"));
    return;
  }
  reportDrawerVisible.value = true;
};

const handleExportReport = async (reports?: CameraReport[]) => {
  try {
    if (!reportList.value.length) {
      await queryCamReport(false);
    }

    if (!reportList.value.length) {
      message.warning(t("smartCommunity.reportNoContent"));
      return;
    }

    const reportsToExport =
      reports && reports.length ? reports : [...reportList.value];

    downloadReportFile(
      buildReportExportContent(reportsToExport),
      dayjs().format("YYYYMMDD-HHmmss"),
    );
    message.success(t("smartCommunity.exportSuccess"));
  } catch {
    message.error(t("smartCommunity.exportFailed"));
  }
};

const refreshActivityList = () => {
  void queryCamFridgeList();
  void queryRecordings();
};

const refreshDashboardData = () => {
  void queryCamReport();
};

const stopLiveStreamPlayback = () => {
  if (liveReconnectTimer !== null) {
    window.clearTimeout(liveReconnectTimer);
    liveReconnectTimer = null;
  }

  cleanupLiveStream?.();
  cleanupLiveStream = null;

  const video = liveVideoRef.value;
  if (!video) {
    return;
  }

  try {
    video.pause();
  } catch {}
};

// The upstream ffmpeg session can end at any time (idle kill, transcoder
// restart, server-side backpressure disconnect). Retry with backoff instead of
// leaving the element frozen on its last decoded frame.
const scheduleLiveStreamReconnect = () => {
  if (
    liveReconnectTimer !== null ||
    document.hidden ||
    !isLiveMode.value ||
    !activeRecord.value.videoSrc
  ) {
    return;
  }

  const delay = liveReconnectDelay;
  liveReconnectDelay = Math.min(delay * 2, LIVE_RECONNECT_MAX_DELAY_MS);
  liveReconnectTimer = window.setTimeout(() => {
    liveReconnectTimer = null;
    void startLiveStreamPlayback();
  }, delay);
};

const startLiveStreamPlayback = async () => {
  stopLiveStreamPlayback();
  await nextTick();

  const video = liveVideoRef.value;
  if (
    !video ||
    !isLiveMode.value ||
    !activeRecord.value.videoSrc ||
    !("MediaSource" in window)
  ) {
    return;
  }

  const controller = new AbortController();
  const mediaSource = new MediaSource();
  const objectUrl = URL.createObjectURL(mediaSource);
  const appendQueue: ArrayBuffer[] = [];
  let queuedBytes = 0;
  let sourceBuffer: SourceBuffer | null = null;
  let reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  let disposed = false;
  let playbackStarted = false;
  let watchdogTimer: number | null = null;
  let userPaused = false;

  const seekToLiveEdge = (resume = true) => {
    if (!sourceBuffer || disposed || !sourceBuffer.buffered.length) {
      return;
    }

    const start = sourceBuffer.buffered.start(0);
    const end = sourceBuffer.buffered.end(sourceBuffer.buffered.length - 1);
    video.currentTime = Math.max(start, end - 0.1);

    if (resume) {
      void video.play().catch((error) => {
        console.error("[live] autoplay failed:", error);
      });
    }
  };

  // Without this the element stays frozen forever once the playhead falls out
  // of the buffered range — nothing else ever moves it back to the live edge.
  const watchLiveEdge = () => {
    if (userPaused || !sourceBuffer || disposed || !sourceBuffer.buffered.length) {
      return;
    }

    const start = sourceBuffer.buffered.start(0);
    const end = sourceBuffer.buffered.end(sourceBuffer.buffered.length - 1);
    const current = video.currentTime;

    if (current < start || end - current > LIVE_EDGE_TOLERANCE_SECONDS) {
      seekToLiveEdge();
      return;
    }

    if (video.paused) {
      void video.play().catch(() => undefined);
    }
  };

  // A pause event can only come from the viewer here — a stalled element stays
  // `paused === false`. Honour it, and rejoin the live edge on resume.
  const handlePause = () => {
    if (!disposed) {
      userPaused = true;
    }
  };

  const handlePlay = () => {
    userPaused = false;
    if (!sourceBuffer || disposed || !sourceBuffer.buffered.length) {
      return;
    }
    if (video.currentTime < sourceBuffer.buffered.start(0)) {
      seekToLiveEdge(false);
    }
  };

  const pumpQueue = () => {
    if (!sourceBuffer || sourceBuffer.updating || disposed) {
      return;
    }

    if (sourceBuffer.buffered.length) {
      const start = sourceBuffer.buffered.start(0);
      const end = sourceBuffer.buffered.end(sourceBuffer.buffered.length - 1);
      // Never evict past the playhead: dropping the range that holds
      // currentTime strands playback outside the buffered region. While the
      // viewer has deliberately paused, let it slide — resuming rejoins live.
      const evictEnd = userPaused
        ? end - RETAIN_STREAM_BUFFER_SECONDS
        : Math.min(end - RETAIN_STREAM_BUFFER_SECONDS, video.currentTime - 1);
      if (end - start > MAX_STREAM_BUFFER_SECONDS && evictEnd > start) {
        sourceBuffer.remove(start, evictEnd);
        return;
      }
    }

    const chunk = appendQueue.shift();
    if (!chunk) {
      return;
    }

    queuedBytes -= chunk.byteLength;
    sourceBuffer.appendBuffer(chunk);
  };

  const handleUpdateEnd = () => {
    if (!sourceBuffer || disposed) {
      return;
    }

    if (!playbackStarted && sourceBuffer.buffered.length) {
      playbackStarted = true;
      seekToLiveEdge();
    }

    pumpQueue();
  };

  const handleVideoError = () => {
    if (disposed) {
      return;
    }

    console.error("[live] media element error:", video.error?.message);
    dispose();
    scheduleLiveStreamReconnect();
  };

  const dispose = () => {
    if (disposed) {
      return;
    }

    disposed = true;
    controller.abort();
    void reader?.cancel().catch(() => undefined);
    mediaSource.removeEventListener("sourceopen", handleSourceOpen);
    sourceBuffer?.removeEventListener("updateend", handleUpdateEnd);
    video.removeEventListener("error", handleVideoError);
    video.removeEventListener("pause", handlePause);
    video.removeEventListener("play", handlePlay);
    if (watchdogTimer !== null) {
      window.clearInterval(watchdogTimer);
      watchdogTimer = null;
    }
    appendQueue.length = 0;
    queuedBytes = 0;

    if (mediaSource.readyState === "open") {
      try {
        mediaSource.endOfStream();
      } catch {
        // The stream may already be closing after an upstream disconnect.
      }
    }

    video.pause();
    video.removeAttribute("src");
    video.load();
    URL.revokeObjectURL(objectUrl);
  };

  async function handleSourceOpen() {
    try {
      if (disposed) {
        return;
      }

      sourceBuffer = mediaSource.addSourceBuffer(
        'video/mp4; codecs="avc1.42C01F"',
      );
      sourceBuffer.addEventListener("updateend", handleUpdateEnd);
      const response = await fetch(activeRecord.value.videoSrc, {
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new Error(`Live stream returned HTTP ${response.status}`);
      }

      liveReconnectDelay = LIVE_RECONNECT_MIN_DELAY_MS;
      reader = response.body.getReader();
      while (!disposed) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        if (queuedBytes + value.byteLength > MAX_STREAM_QUEUE_BYTES) {
          throw new Error("Live stream append queue exceeded its limit");
        }

        const chunk = value.slice().buffer as ArrayBuffer;
        appendQueue.push(chunk);
        queuedBytes += chunk.byteLength;
        pumpQueue();
      }

      // Upstream closed the response — the transcoder died or was idle-killed.
      if (!disposed) {
        dispose();
        scheduleLiveStreamReconnect();
      }
    } catch (error) {
      if (
        !disposed &&
        !(error instanceof DOMException && error.name === "AbortError")
      ) {
        console.error("[live] stream playback failed:", error);
        dispose();
        scheduleLiveStreamReconnect();
      }
    }
  }

  cleanupLiveStream = dispose;
  video.src = objectUrl;
  video.muted = true;
  video.defaultMuted = true;
  video.autoplay = true;
  video.addEventListener("error", handleVideoError);
  video.addEventListener("pause", handlePause);
  video.addEventListener("play", handlePlay);
  watchdogTimer = window.setInterval(watchLiveEdge, LIVE_WATCHDOG_INTERVAL_MS);
  mediaSource.addEventListener("sourceopen", handleSourceOpen, { once: true });
};

const handleVisibilityChange = () => {
  if (document.hidden) {
    stopLiveStreamPlayback();
    return;
  }

  if (isLiveMode.value) {
    liveReconnectDelay = LIVE_RECONNECT_MIN_DELAY_MS;
    void startLiveStreamPlayback();
  }
};

const clearRecordingSession = () => {
  recordingSession.value = null;
  recordingElapsedSeconds.value = 0;
  recordingErrorStreak = 0;
};

const startRecordingSegment = (
  segment: RecordingSegment,
  offsetSeconds: number,
) => {
  // Leaving live mode tears down the MSE stream via the isLiveMode watcher.
  isLiveMode.value = false;
  recordingElapsedSeconds.value = offsetSeconds;
  recordingSession.value = { segment, offsetSeconds };
};

const handleSeekRecording = (timeMs: number) => {
  const segment = findRecordingAt(recordingList.value, timeMs);
  if (!segment) {
    message.warning(t("smartCommunity.noRecordingAtTime"));
    return;
  }

  startRecordingSegment(segment, Math.max(0, (timeMs - segment.startMs) / 1000));
};

const handleRecordingLoaded = (event: Event) => {
  const video = event.target as HTMLVideoElement;
  const session = recordingSession.value;
  if (!session) {
    return;
  }

  recordingErrorStreak = 0;
  // The DB duration and the muxed file can disagree by a frame or two.
  const target = Math.min(
    session.offsetSeconds,
    Math.max((video.duration || 0) - 0.1, 0),
  );
  if (Number.isFinite(target) && target > 0) {
    video.currentTime = target;
  }

  void video.play().catch(() => undefined);
};

const handleRecordingTimeUpdate = (event: Event) => {
  recordingElapsedSeconds.value = (event.target as HTMLVideoElement).currentTime;
};

const handleRecordingEnded = () => {
  const session = recordingSession.value;
  if (!session) {
    return;
  }

  const next = findNextRecording(recordingList.value, session.segment.startMs);
  if (!next) {
    message.info(t("smartCommunity.recordingReachedEnd"));
    return;
  }

  startRecordingSegment(next, 0);
};

// Retention can delete the mp4 while the DB row survives. Skip over a few dead
// segments, then give up rather than racing through the rest of the day.
const handleRecordingError = () => {
  const session = recordingSession.value;
  recordingErrorStreak += 1;

  const next =
    recordingErrorStreak <= 3 && session
      ? findNextRecording(recordingList.value, session.segment.startMs)
      : null;

  if (!next) {
    clearRecordingSession();
    message.warning(t("smartCommunity.recordingLoadFailed"));
    return;
  }

  startRecordingSegment(next, 0);
};

const handleHistoryRecordSelect = (record: ActivityRecord) => {
  clearRecordingSession();
  activeRecord.value = record;
  isLiveMode.value = false;
};

const switchToLive = () => {
  clearRecordingSession();
  activeRecord.value = buildFallbackActiveRecord(selectedDate.value);
  isLiveMode.value = true;
};

watch(
  () => [isLiveMode.value, activeRecord.value.videoSrc] as const,
  async ([liveMode, videoSrc]) => {
    if (!liveMode || !videoSrc) {
      stopLiveStreamPlayback();
      return;
    }

    await startLiveStreamPlayback();
  },
  { immediate: true },
);

onMounted(() => {
  document.addEventListener("visibilitychange", handleVisibilityChange);
  activeRecord.value = buildFallbackActiveRecord();
  liveNow.value = dayjs();
  void queryCamFridgeList({ showLoading: true });
  void queryRecordings();
  void queryCamReport();
  activityPollingTimer = window.setInterval(refreshActivityList, 30 * 1000);
  reportPollingTimer = window.setInterval(refreshDashboardData, 3 * 60 * 1000);
  liveClockTimer = window.setInterval(() => {
    liveNow.value = dayjs();
  }, 1000);
});

watch(selectedSourceId, () => {
  clearRecordingSession();
  activeRecord.value = buildFallbackActiveRecord(selectedDate.value);
  isLiveMode.value = true;
  reportDrawerVisible.value = false;
  resetReportData();
  void queryCamFridgeList({ showLoading: true });
  void queryRecordings();
  void queryCamReport();
});

onUnmounted(() => {
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  stopLiveStreamPlayback();

  if (activityPollingTimer !== null) {
    window.clearInterval(activityPollingTimer);
  }

  if (reportPollingTimer !== null) {
    window.clearInterval(reportPollingTimer);
  }

  if (liveClockTimer !== null) {
    window.clearInterval(liveClockTimer);
  }
});
</script>

<style scoped lang="less">
.monitor-panel {
  height: 100%;
  min-height: 0;
  .flex-column;
  gap: 12px;
  width: 100%;
  padding: 14px 12px;
  background: var(--bg-content-color);
  border-radius: 24px;
  border: 1px solid var(--border-primary);
}

.panel-header {
  gap: 12px;
}

.panel-controls {
  gap: 10px;
  flex-wrap: wrap;
  margin-left: auto;
}

.date-switcher {
  gap: 8px;
  padding: 7px 10px;
  border-radius: 14px;
  background: var(--color-primaryBg);
}

.export-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-primary);
  border-radius: 14px;
  background: var(--color-primary);
  color: var(--color-white);
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 10px 20px var(--bg-box-shadow);

  &:hover,
  &:focus {
    color: var(--color-white) !important;
    border-color: var(--color-primary) !important;
    background: var(--color-primary-hover) !important;
  }
}

.report-btn {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border-primary);
  border-radius: 14px;
  background: var(--surface-card-bg);
  color: var(--font-main-color);
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 8px 18px var(--bg-box-shadow);

  &:hover,
  &:focus {
    color: var(--color-primary-hover) !important;
    border-color: var(--color-primary) !important;
    background: var(--surface-card-bg) !important;
  }
}


.panel-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--font-main-color);
}

.video-stage-shell {
  width: 100%;
  border-radius: 24px;
  background: var(--surface-panel-bg);
  border: 1px solid var(--border-primary);
}

.video-stage {
  position: relative;
  min-height: 240px;
  border-radius: 20px;
  overflow: hidden;
  background: var(--media-stage-bg);
  box-shadow: 0 14px 28px var(--bg-box-shadow);
}

.main-empty-state {
  height: 240px;
  color: var(--media-control-text-muted);
  font-size: 14px;
}

.live-player {
  width: 100%;
  height: 240px;
  display: block;
  border-radius: 20px;
  background: var(--media-stage-bg);
  object-fit: contain;
  box-shadow:
    inset 0 0 0 1px var(--surface-overlay-border),
    0 18px 34px var(--bg-box-shadow);
}

.video-topbar,
.video-content {
  position: absolute;
  z-index: 2;
  left: 16px;
  right: 16px;
}

.video-topbar {
  top: 14px;
  gap: 10px;
}

.video-topbar-actions {
  gap: 10px;
}

.realtime-pill {
  display: inline-flex;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 999px;
  border: 1px solid var(--surface-overlay-border);
  background: var(--media-control-bg);
  backdrop-filter: blur(8px);
}

.realtime-pill-value {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-white);
}

.video-mode-tag {
  width: fit-content;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--color-errorBg);
  border: 1px solid var(--surface-overlay-border);
  color: var(--font-main-color);
  font-size: 11px;
  letter-spacing: 1.3px;

  &.live {
    background: var(--color-successBg);
    color: var(--font-main-color);
  }
}

.back-live-btn {
  border: 1px solid var(--surface-overlay-border);
  background: var(--surface-overlay-button-bg);
  color: var(--color-primary-hover);
  font-weight: 600;
  box-shadow: 0 10px 18px var(--bg-box-shadow);

  &:hover,
  &:focus {
    color: var(--color-primary-hover) !important;
    border-color: var(--surface-overlay-border-strong) !important;
    background: var(--surface-overlay-button-hover-bg) !important;
  }
}

.video-content {
  bottom: 74px;
  max-width: 330px;
  color: var(--color-white);
  pointer-events: none;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.38);
}

.video-kicker {
  font-size: 11px;
  opacity: 0.86;
}

.video-title {
  margin-top: 8px;
  font-size: 22px;
  font-weight: 700;
}

.video-time {
  margin-top: 8px;
  width: fit-content;
  padding: 5px 9px;
  border-radius: 10px;
  background: var(--surface-overlay-soft);
  font-size: 11px;
  font-weight: 600;
}

:deep(.main-player) {
  width: 100%;
  height: 240px;
}

:deep(.main-player .d-player-wrap),
:deep(.main-player .d-player-video),
:deep(.main-player .d-player-video-main),
:deep(.main-player video) {
  width: 100%;
  height: 240px;
  border-radius: 20px;
}

:deep(.main-player .d-player-wrap) {
  background: var(--media-stage-bg);
  border-radius: 20px;
  box-shadow:
    inset 0 0 0 1px var(--surface-overlay-border),
    0 18px 34px var(--bg-box-shadow);
  font-family: inherit;
}

:deep(.main-player .d-player-video-main) {
  object-fit: cover;
}

:deep(.main-player .d-player-top) {
  display: none;
}

:deep(.main-player .d-player-state) {
  bottom: 0;
}

:deep(.main-player .d-player-control) {
  height: 62px;
  border-radius: 0 0 20px 20px;
}

:deep(.main-player .d-control-progress) {
  height: 12px;
}

:deep(.main-player .d-control-tool) {
  top: 12px;
  padding: 0 14px;
  background: var(--media-control-bg-strong);
  backdrop-filter: blur(14px);
}

:deep(.main-player .d-play-btn) {
  width: 58px;
  height: 58px;
  border: 1px solid var(--surface-overlay-border);
  background: var(--media-control-bg);
  box-shadow: 0 10px 24px var(--bg-box-shadow);
  backdrop-filter: blur(10px);
  opacity: 0;
  transform: scale(0.94);
  transition:
    opacity 0.2s ease,
    transform 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

:deep(.main-player:hover .d-play-btn),
:deep(.main-player .d-play-btn:hover) {
  opacity: 1;
  transform: scale(1);
  border-color: var(--surface-overlay-border-strong);
  background: var(--media-control-hover-bg);
}

:deep(.main-player .d-control-progress .d-progress-bar) {
  height: 4px;
}

:deep(.main-player .d-control-progress:hover .d-progress-bar) {
  height: 6px;
}

:deep(.main-player .d-slider__runway) {
  background: var(--surface-overlay-soft) !important;
}

:deep(.main-player .d-slider__bar) {
  background: var(--color-primary) !important;
}

:deep(.main-player .d-slider__bar::before) {
  width: 10px !important;
  height: 10px !important;
  box-shadow: 0 0 0 4px var(--border-primary) !important;
}

:deep(.main-player .d-tool-time) {
  font-size: 11px;
  font-weight: 500;
  color: var(--color-white);
  letter-spacing: 0.2px;
}

:deep(.main-player .d-tool-time .total-time) {
  color: var(--media-control-text-muted);
}

:deep(.main-player .d-tool-item) {
  min-width: 30px;
  height: 30px !important;
  margin: 0 2px;
  padding: 0 6px !important;
  border-radius: 10px;
  transition:
    background 0.2s ease,
    color 0.2s ease;
}

:deep(.main-player .d-tool-item:hover) {
  background: var(--surface-overlay-soft);
}

:deep(.main-player .d-tool-item-main) {
  border: 1px solid var(--surface-overlay-soft);
  background: var(--media-control-bg-strong) !important;
  backdrop-filter: blur(12px);
}

:deep(.main-player .volume-box) {
  height: 136px !important;
}

:deep(.ant-picker) {
  border: none;
  background: transparent;
  box-shadow: none;
}

@media (max-width: 768px) {
  .panel-controls {
    width: 100%;
    justify-content: space-between;
  }

  .monitor-panel {
    padding: 12px 0;
  }

  .panel-header {
    align-items: flex-start;
  }

  .panel-title {
    font-size: 20px;
  }

  .video-topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .video-content {
    bottom: 66px;
  }

  .video-topbar-actions {
    width: 100%;
    justify-content: space-between;
  }

  .live-player,
  :deep(.main-player),
  :deep(.main-player .d-player-wrap),
  :deep(.main-player .d-player-video),
  :deep(.main-player .d-player-video-main),
  :deep(.main-player video) {
    height: 210px;
  }
}
</style>
