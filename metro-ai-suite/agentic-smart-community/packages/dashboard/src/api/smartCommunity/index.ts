// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
import dayjs from "dayjs";
import request from "../request";

interface MonitorResponse {
  id: string;
  name: string;
  status: "online" | "offline" | "error";
  useCase: string;
}

interface ActivityResponse {
  task: Record<string, any>;
  event?: Record<string, any>;
  alert?: Record<string, any>;
}

interface RecordingResponse {
  id: number;
  startTime: string;
  endTime: string;
  durationSeconds?: number;
  fileSizeBytes?: number;
}

interface ReportResponse {
  id: number;
  monitorId: string;
  periodStart: string;
  reportText?: string;
  eventCount?: number;
  motionCount?: number;
  promptTokens?: number;
  imageTokens?: number;
  completionTokens?: number;
  status: string;
  createdAt: string;
}

export interface AgentFrameworkOption {
  id: "openclaw";
  label: string;
  defaultUrl: string;
}

export interface DashboardConfig {
  chat: "configured" | "unconfigured";
  frameworks: AgentFrameworkOption[];
}

export const getMonitors = async (params: Object) => {
  const monitors = await request<unknown, MonitorResponse[]>({
    url: "/api/monitors",
    method: "get",
    params,
  });

  return { monitors };
};

export const getDashboardConfig = () => {
  return request<unknown, DashboardConfig>({
    url: "/api/dashboard/config",
    method: "get",
  });
};

export const configureAgentFramework = (data: {
  framework: AgentFrameworkOption["id"];
  url: string;
  token: string;
}) => {
  return request({
    url: "/api/dashboard/chat/config",
    method: "post",
    data,
  });
};

export const getCameraActivityList = async (params: Record<string, unknown>) => {
  const activities = await request<unknown, ActivityResponse[]>({
    url: "/api/tasks",
    method: "get",
    params: {
      monitor_id: params.source_id,
      date: params.date,
    },
  });

  return {
    tasks: activities.map(({ task, event, alert }) => ({
      ...task,
      source_id: task.monitorId,
      clip_start_time: task.clipStartTime || task.createdAt,
      clip_duration: task.clipDuration ?? event?.durationSeconds ?? 0,
      clip_file_path: task.summaryClipInput || "",
      summary_text: task.summaryText || alert?.description || "",
      created_at: task.createdAt,
      event_type: event?.motionType || "static",
      actual_alert: alert?.notified === true,
      alert: alert
        ? task.alert_type || task.event || task.severity || "alert"
        : null,
    })),
  };
};

export const getCameraRecordings = async (params: Record<string, unknown>) => {
  const recordings = await request<unknown, RecordingResponse[]>({
    url: "/api/recordings",
    method: "get",
    params: {
      monitor_id: params.source_id,
      date: params.date,
    },
  });

  return {
    recordings: recordings.map((recording) => ({
      id: recording.id,
      startMs: dayjs(recording.startTime).valueOf(),
      endMs: dayjs(recording.endTime).valueOf(),
      durationSeconds: recording.durationSeconds ?? 0,
      fileSizeBytes: recording.fileSizeBytes ?? 0,
    })),
  };
};

export const buildRecordingStreamUrl = (recordingId: number, sourceId: string) => {
  return `/api/recordings/${recordingId}/stream?monitor_id=${encodeURIComponent(sourceId)}`;
};

export const getCamReport = async (params: Record<string, unknown>) => {
  const reports = await request<unknown, ReportResponse[]>({
    url: "/api/reports",
    method: "get",
    params: {
      monitor_id: params.source_id,
      date: params.date,
    },
  });

  return {
    reports: reports.map((report) => ({
      id: report.id,
      source_id: report.monitorId,
      report_date: report.periodStart.slice(0, 10),
      report_text: report.reportText || "",
      event_count: report.eventCount || 0,
      motion_count: report.motionCount || 0,
      prompt_tokens: report.promptTokens || 0,
      image_tokens: report.imageTokens || 0,
      completion_tokens: report.completionTokens || 0,
      status: report.status,
      created_at: report.createdAt,
    })),
  };
};

export const requestGenerateReport = (data: Record<string, unknown>) => {
  return request({
    url: "/api/reports/generate",
    method: "post",
    data: {
      monitor_id: data.source_id,
      type: "daily",
    },
    showLoading: true,
    showSuccessMsg: true,
    successMsg: "smartCommunity.generateReportSuccess",
  });
};

export const getTaskTokens = (params: Object) => {
  return request({
    url: "/api/stats",
    method: "get",
    params: {
      monitor_id: (params as Record<string, unknown>).source_id,
      date: (params as Record<string, unknown>).date,
    },
  });
};

export const getTokenStats = () => {
  return request({
    url: "/api/router/stats",
    method: "get",
  });
};

export const requestTokenRest = () => {
  return request({
    url: "/api/router/stats/reset",
    method: "post",
    showLoading: true,
    showSuccessMsg: true,
    successMsg: "monitor.resetSuccess",
  });
};
