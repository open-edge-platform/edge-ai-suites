import type { ServerConfig } from "../config.js";
import type { SmartBuildingDB } from "@smartbuilding-video/db";
import type { VideoSummaryClient } from "@smartbuilding-video/tools";
import type { VideoSummaryYield } from "./video-summary-yield.js";
import type { AlertCallback } from "./index.js";
import { evaluateWithOverride, normalizeSummaryTextBySchema, parseSummaryFields } from "@smartbuilding-video/tools";
import { logger } from "../logger.js";

export class TaskPoller {
  private intervals: Map<string, ReturnType<typeof setInterval>> = new Map();
  // Tracks the currently in-flight poll promise per monitor for graceful stop
  private activePoll: Map<string, Promise<void>> = new Map();
  private config: ServerConfig;
  private db: SmartBuildingDB;
  private videoSummaryClient: VideoSummaryClient;
  private yieldManager: VideoSummaryYield;
  private onAlert?: AlertCallback;

  constructor(
    config: ServerConfig,
    db: SmartBuildingDB,
    videoSummaryClient: VideoSummaryClient,
    yieldManager: VideoSummaryYield,
    onAlert?: AlertCallback,
  ) {
    this.config = config;
    this.db = db;
    this.videoSummaryClient = videoSummaryClient;
    this.yieldManager = yieldManager;
    this.onAlert = onAlert;
  }

  startPolling(monitorId: string): void {
    if (this.intervals.has(monitorId)) return;

    const interval = setInterval(() => {
      const promise = this.poll(monitorId).then(() => {
        this.activePoll.delete(monitorId);
      });
      this.activePoll.set(monitorId, promise);
    }, this.config.pollIntervalMs);

    this.intervals.set(monitorId, interval);
  }

  async stopPolling(monitorId: string): Promise<void> {
    const interval = this.intervals.get(monitorId);
    if (interval) {
      clearInterval(interval);
      this.intervals.delete(monitorId);
    }
    // Wait for any in-flight poll to finish before returning
    const inflight = this.activePoll.get(monitorId);
    if (inflight) {
      await inflight;
      this.activePoll.delete(monitorId);
    }
  }

  private async poll(monitorId: string): Promise<void> {
    const tasks = this.db.getPendingTasks(monitorId, 1);
    if (tasks.length === 0) return;

    const task = tasks[0];
    const monitor = this.db.getMonitor(monitorId);
    const useCase = monitor?.useCase ?? "";
    const useCaseCfg = this.config.useCaseDict[useCase];
    const summaryTaskName = monitor?.videoSummaryTask ?? "";

    try {
      await this.yieldManager.acquire();
      this.db.updateTaskStatus(task.id, "processing");

      const videoPath = task.summaryClipInput ?? "";
      const t0 = Date.now();
      // Per-clip summarize tuning is configurable via use_case_dict.<useCase>.summarize.
      // Defaults below match the legacy smarthome stream_monitor config: LOCAL_PROMPT
      // only (levels=1), no T-1 dependency (method=SIMPLE), 2 fps sampling.
      const summarizeCfg = useCaseCfg?.summarize ?? {};
      const result = await this.videoSummaryClient.summarize({
        video: videoPath,
        task: summaryTaskName,
        method: summarizeCfg.method ?? "SIMPLE",
        processor_kwargs: {
          levels: summarizeCfg.processor_kwargs?.levels ?? 1,
          level_sizes: summarizeCfg.processor_kwargs?.level_sizes ?? [-1],
          process_fps: summarizeCfg.processor_kwargs?.process_fps ?? 2,
          ...(summarizeCfg.processor_kwargs?.chunking_method
            ? { chunking_method: summarizeCfg.processor_kwargs.chunking_method }
            : {}),
        },
      });
      const latencySeconds = (Date.now() - t0) / 1000;

      // VLM output parser: schema-aware field extraction. Schema is owned per use
      // case — parse only the columns THIS use case declares, so one use case's
      // fields never leak into another's parsing or required-field check.
      const extensions = useCaseCfg?.schema?.video_summary_tasks?.extensions ?? [];
      const requiredNames = extensions.filter((e) => e.required).map((e) => e.name);
      const parsed = parseSummaryFields(result.summary ?? "", extensions, requiredNames);
      if (parsed.missingRequired.length > 0) {
        logger.warn(`[task-poller] task ${task.id} (${monitorId}) missing required schema fields: ${parsed.missingRequired.join(", ")}`);
      }
      const normalizedSummaryText = normalizeSummaryTextBySchema(result.summary ?? "", extensions, parsed.fields);

      // Persist summary text + extension fields + service usage in one UPDATE.
      this.db.updateTaskStatus(task.id, "completed", normalizedSummaryText, {
        latencySeconds,
        promptTokens: result.usage?.prompt_tokens,
        imageTokens: result.usage?.image_tokens,
        completionTokens: result.usage?.completion_tokens,
      }, parsed.fields);

      // Evaluate rules via rule engine. Override path (Python script) is derived
      // from config.useCaseDict[monitor.useCase].evaluate_rules_path; absent → defaultRuleEvaluator.
      const overridePath = useCaseCfg?.evaluate_rules_path ?? null;
      const ruleCtx = {
        monitorId,
        useCase,
        taskId: task.id,
        summaryText: result.summary ?? "",
        payload: {
          fields: parsed.fields,
        },
      };
      const ruleResult = await evaluateWithOverride(ruleCtx, overridePath);

      if (ruleResult.shouldAlert) {
        this.db.createAlert({
          monitorId,
          taskId: task.id,
          eventId: task.eventId,
          useCase,
          description: ruleResult.alertMessage,
          notified: true,
        });
        if (this.onAlert) {
          this.onAlert(monitorId);
        }
      }
    } catch (err: any) {
      logger.error(`[task-poller] task ${task.id} (${monitorId}) failed: ${err.message}`);
      this.db.updateTaskStatus(task.id, "failed", undefined, { errorMessage: err.message });
    } finally {
      this.yieldManager.release();
    }
  }
}
