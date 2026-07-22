import type { ServerConfig } from "../config.js";
import type { SmartBuildingDB } from "@smartbuilding-video/db";
import type { VideoSummaryClient } from "@smartbuilding-video/tools";
import { TaskPoller } from "./task-poller.js";
import { VideoSummaryYield } from "./video-summary-yield.js";

export interface MonitorWorker {
  monitorId: string;
  running: boolean;
}

// Notifies MCP server that an alert was created for a monitor (triggers resource notification)
export type AlertCallback = (monitorId: string) => void;

export class WorkerService {
  readonly workers: Map<string, MonitorWorker> = new Map();
  private poller: TaskPoller;

  constructor(
    config: ServerConfig,
    db: SmartBuildingDB,
    summaryClient: VideoSummaryClient,
    onAlert?: AlertCallback,
  ) {
    const yieldManager = new VideoSummaryYield(config.videoSummaryMaxConcurrent);
    this.poller = new TaskPoller(config, db, summaryClient, yieldManager, onAlert);
  }

  start(monitorId: string): void {
    if (this.workers.has(monitorId)) return;
    this.workers.set(monitorId, { monitorId, running: true });
    this.poller.startPolling(monitorId);
  }

  async stop(monitorId: string): Promise<void> {
    const worker = this.workers.get(monitorId);
    if (worker) {
      worker.running = false;
      await this.poller.stopPolling(monitorId);
      this.workers.delete(monitorId);
    }
  }

  listWorkers(): MonitorWorker[] {
    return [...this.workers.values()];
  }

  async stopAll(): Promise<void> {
    await Promise.all([...this.workers.keys()].map((id) => this.stop(id)));
  }
}
