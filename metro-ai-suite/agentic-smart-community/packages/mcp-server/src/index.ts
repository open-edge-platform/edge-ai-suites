import { mkdirSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { SmartBuildingDB, SchemaManager } from "@smartbuilding-video/db";
import { VideoSummaryClient } from "@smartbuilding-video/tools";
import { registerTools } from "./tools.js";
import { registerResources } from "./resources.js";
import { loadConfig, loadMonitorsConfig, type ServerConfig } from "./config.js";
import { WorkerService } from "./video-worker/index.js";
import { EventsEndpoint } from "./events-endpoint.js";
import { logger } from "./logger.js";
import { autoRegisterMonitors } from "./monitor-bootstrap.js";
import { startStorageCleaner } from "./storage-cleaner.js";
import { startKeepaliveSender } from "./keepalive-sender.js";
import { McpSubscriberRegistry } from "./mcp-subscriber-registry.js";
import { startSessionSweeper } from "./session-sweeper.js";

/**
 * Build an McpServer for a single MCP session. Stateful HTTP creates one per new sessionId;
 * stdio creates one for the entire process. DB / config / workerService are shared across
 * instances. `getSessionId` is threaded into the subscribe/unsubscribe handlers so
 * `notifications/resources/updated` can broadcast to the right sessions when alerts fire. It's a
 * callback (not a plain string) because for stateful HTTP the transport's sessionId isn't known
 * until the `initialize` handshake completes — later than server construction.
 */
function createMcpServer(
  config: ServerConfig,
  db: SmartBuildingDB,
  workerService: WorkerService,
  summaryClient: VideoSummaryClient,
  subscriberRegistry: McpSubscriberRegistry,
  getSessionId: () => string,
): McpServer {
  const server = new McpServer({
    name: "smartbuilding-video",
    version: "0.1.0",
  });

  registerTools(server, config, db, workerService, summaryClient);
  registerResources(server, config, db, subscriberRegistry, getSessionId);

  return server;
}

async function main() {
  const configPath = process.argv.includes("--config")
    ? process.argv[process.argv.indexOf("--config") + 1]
    : undefined;

  const monitorsPath = process.argv.includes("--monitors")
    ? process.argv[process.argv.indexOf("--monitors") + 1]
    : undefined;

  const transportMode = process.argv.includes("--http") ? "http" : "stdio";

  const config: ServerConfig = loadConfig(configPath);

  if (monitorsPath) {
    try {
      config.monitors = loadMonitorsConfig(monitorsPath);
      logger.info(`[config] loaded ${Object.keys(config.monitors).length} monitor(s) from ${monitorsPath}`);

      // Reference integrity: every monitor.use_case must exist in config.useCaseDict
      const knownUseCases = Object.keys(config.useCaseDict);
      const badRefs: string[] = [];
      for (const [id, m] of Object.entries(config.monitors)) {
        if (!knownUseCases.includes(m.use_case)) {
          badRefs.push(`${id} → "${m.use_case}"`);
        }
      }
      if (badRefs.length > 0) {
        throw new Error(
          `monitors reference unknown use_case keys: [${badRefs.join(", ")}]. ` +
          `Declared in config.yaml use_case_dict: [${knownUseCases.join(", ")}]`,
        );
      }
    } catch (err: any) {
      logger.error(`[config] failed to load --monitors ${monitorsPath}: ${err.message}`);
      process.exit(1);
    }
  }

  mkdirSync(config.dataDir, { recursive: true });
  mkdirSync(config.segmentsDir, { recursive: true });
  mkdirSync(config.reportsLogsDir, { recursive: true });
  mkdirSync(config.monitorsLogsDir, { recursive: true });

  const db = new SmartBuildingDB(config.dbPath);
  db.initialize();

  {
    // Schema is owned per use case (no global shared schema). Apply each use
    // case's declared columns to the shared video_summary_tasks table. ALTER is
    // idempotent, so use cases that declare the same column (event/desc/...) only
    // add it once, and a restart re-applies safely.
    const schemaManager = new SchemaManager((db as any).db);
    const added: string[] = [];
    const warnings: string[] = [];
    for (const uc of Object.values(config.useCaseDict)) {
      if (!uc.schema) continue;
      const result = schemaManager.applySchema(uc.schema);
      added.push(...result.added);
      warnings.push(...result.warnings);
    }
    if (added.length > 0) {
      logger.info(`[schema] Added columns: ${Array.from(new Set(added)).join(", ")}`);
    }
    if (warnings.length > 0) {
      logger.warn(`[schema] ${Array.from(new Set(warnings)).join(", ")}`);
    }
  }

  const subscriberRegistry = new McpSubscriberRegistry();
  let stopSessionSweeper: (() => void) | undefined;

  // Broadcast `notifications/resources/updated` to every MCP session subscribed to this monitor's
  // alerts uri. See docs/framework-adapters/README.md for the end-to-end contract.
  const onAlert = (monitorId: string) => {
    const uri = `smartbuilding://monitor/${monitorId}/alerts`;
    const subs = subscriberRegistry.findSubscribers(uri);
    if (subs.length === 0) {
      logger.debug(`[worker] alert for ${monitorId} — no subscribers, dropped notification`);
      return;
    }
    for (const { server } of subs) {
      server.server.sendResourceUpdated({ uri }).catch((err) =>
        logger.warn(`[worker] sendResourceUpdated ${uri} failed: ${err.message}`),
      );
    }
  };

  const summaryClient = new VideoSummaryClient(config.summaryService.url, config.summaryService.pathRemap);
  const workerService = new WorkerService(config, db, summaryClient, onAlert);

  if (transportMode === "http") {
    const app = createMcpExpressApp();

    // Stateful HTTP: one McpServer + transport per sessionId. Required for `resources/subscribe`
    // to persist across requests. Session lifetimes end when the transport closes (client DELETE
    // or explicit close), at which point we unregister from the subscriber registry.
    app.all("/mcp", async (req, res) => {
      logger.debug(`[mcp] ${req.method} /mcp`);

      const providedSessionId = req.headers["mcp-session-id"] as string | undefined;
      let entry = providedSessionId ? subscriberRegistry.get(providedSessionId) : undefined;

      try {
        if (!entry) {
          // New session — the SDK's StreamableHTTPServerTransport allocates a sessionId
          // during the initialize response when `sessionIdGenerator` is set.
          const transport = new StreamableHTTPServerTransport({
            sessionIdGenerator: () => randomUUID(),
            onsessioninitialized: (sid: string) => {
              subscriberRegistry.register(sid, {
                server,
                transport,
                subscriptions: new Set(),
                lastSeen: Date.now(),
                openSseCount: 0,
              });
              logger.debug(`[mcp] session initialized sid=${sid}`);
            },
          });

          // Session id isn't known at construction time — pass a callback that reads it lazily
          // from the transport once initialize has assigned one (subscribe/unsubscribe always
          // arrive after initialize, so transport.sessionId is set by the time this is called).
          const server = createMcpServer(
            config,
            db,
            workerService,
            summaryClient,
            subscriberRegistry,
            () => transport.sessionId ?? "__pending__",
          );

          transport.onclose = () => {
            const sid = transport.sessionId;
            if (sid) {
              subscriberRegistry.unregister(sid);
              logger.debug(`[mcp] session closed sid=${sid}`);
            }
          };

          await server.connect(transport);
          await transport.handleRequest(req, res, req.body);
          return;
        }

        // Existing session — reuse its transport.
        if (!entry.transport) {
          throw new Error(`stdio session ${providedSessionId} cannot serve HTTP requests`);
        }
        const sid = providedSessionId as string;
        subscriberRegistry.touch(sid); // refresh idle clock on any request

        // A GET opens the standalone SSE stream — the session is "active" for as long as it's held,
        // even with no further requests. Track open/close so the sweeper exempts live subscribers.
        if (req.method === "GET") {
          subscriberRegistry.sseOpened(sid);
          res.on("close", () => subscriberRegistry.sseClosed(sid));
        }
        await entry.transport.handleRequest(req, res, req.body);
      } catch (error) {
        logger.error(`[mcp] ${error}`);
        if (!res.headersSent) {
          res.status(500).json({
            jsonrpc: "2.0",
            error: { code: -32603, message: "Internal server error" },
            id: null,
          });
        }
      }
    });

    const port = config.mcp!.port;
    app.listen(port, () => {
      logger.info(`[mcp-server] Streamable HTTP (stateful) on http://localhost:${port}/mcp`);
    });

    // Evict idle HTTP sessions (no open SSE + no requests past the timeout) so abandoned
    // subscriptions don't leak the registry. stdio mode has a single resident session, so no sweeper.
    stopSessionSweeper = startSessionSweeper(subscriberRegistry, {
      idleTimeoutMs: config.mcp!.sessionIdleTimeoutMs!,
      sweepIntervalMs: config.mcp!.sessionSweepIntervalMs!,
    });

  } else {
    // stdio: single long-lived server registered under a fixed sessionId so onAlert can find it.
    const STDIO_SESSION_ID = "stdio";
    const mcpServer = createMcpServer(config, db, workerService, summaryClient, subscriberRegistry, () => STDIO_SESSION_ID);
    subscriberRegistry.register(STDIO_SESSION_ID, {
      server: mcpServer,
      transport: null,
      subscriptions: new Set(),
      lastSeen: Date.now(),
      openSseCount: 0,
    });
    const transport = new StdioServerTransport();
    await mcpServer.connect(transport);
  }

  const eventsEndpoint = new EventsEndpoint(db, undefined, {
    maxBodyBytes: config.eventsWebhook!.maxBodyBytes,
  });
  await eventsEndpoint.start(config.eventsWebhook!.port);

  // Clean up state from previous crash (analytics sources that DB doesn't know about, etc.)
  await reconcileOnStartup(db, config.videostreamAnalytics.url);

  await autoRegisterMonitors(db, config, workerService);

  // Periodic disk cleanup: logs/monitors + segments/<id>/{recordings,motion_events,queries}
  const stopCleaner = startStorageCleaner(config);

  // Keepalive heartbeat: POST /sources/{id}/keepalive for online monitors so the
  // videostream-analytics watchdog (armed at register_source) doesn't auto-pause them.
  const stopKeepalive = startKeepaliveSender(config, db);

  const shutdown = async () => {
    logger.info("[mcp-server] Shutting down...");
    stopCleaner();
    stopKeepalive();
    stopSessionSweeper?.();
    await workerService.stopAll();
    const onlineMonitors = db.listOnlineMonitors();
    if (onlineMonitors.length > 0) {
      logger.info(`[shutdown] Pausing ${onlineMonitors.length} online monitors in videostream-analytics (${config.videostreamAnalytics.url})`);
      await Promise.all(onlineMonitors.map((m) =>
        fetch(`${config.videostreamAnalytics.url}/sources/${m.id}/pause`, {
          method: "POST", signal: AbortSignal.timeout(3000),
        }).catch(() => {})
      ));
      for (const m of onlineMonitors) db.updateMonitorStatus(m.id, "offline");
    }
    eventsEndpoint.stop();
    db.close();
    process.exit(0);
  };

  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

async function reconcileOnStartup(
  db: SmartBuildingDB,
  analyticsUrl: string,
): Promise<void> {
  let analyticsSources: Map<string, unknown>;
  try {
    const resp = await fetch(`${analyticsUrl}/sources`, { signal: AbortSignal.timeout(5000) });
    if (!resp.ok) {
      logger.warn(`[reconcile] videostream-analytics (${analyticsUrl}) returned HTTP ${resp.status} — skipping startup reconciliation`);
      return;
    }
    const list = (await resp.json()) as any[];
    analyticsSources = new Map(list.map((s: any) => [s.source_id, s]));
  } catch {
    logger.warn(`[reconcile] videostream-analytics (${analyticsUrl}) unreachable — skipping startup reconciliation`);
    return;
  }

  let offlined = 0;
  let deleted = 0;

  // DB-marked-online monitors are crash remnants: mark offline so register_source restarts them.
  const onlineMonitors = db.listOnlineMonitors();
  for (const m of onlineMonitors) {
    if (analyticsSources.has(m.id)) {
      await fetch(`${analyticsUrl}/sources/${m.id}`, { method: "DELETE", signal: AbortSignal.timeout(5000) }).catch(() => {});
      logger.warn(`[reconcile] monitor ${m.id} found in videostream-analytics (${analyticsUrl}) on startup, deleted and marked offline — call register_source to restart`);
    } else {
      logger.warn(`[reconcile] monitor ${m.id} not found in videostream-analytics (${analyticsUrl}) after restart, marked offline — call register_source to restart`);
    }
    db.updateMonitorStatus(m.id, "offline");
    offlined++;
  }

  // Orphans (in analytics but not DB): DB is source of truth.
  const dbIds = new Set(db.listMonitors().map((m) => m.id));
  for (const sourceId of analyticsSources.keys()) {
    if (!dbIds.has(sourceId)) {
      await fetch(`${analyticsUrl}/sources/${sourceId}`, { method: "DELETE", signal: AbortSignal.timeout(5000) }).catch(() => {
        logger.warn(`[reconcile] failed to delete orphan source ${sourceId} from videostream-analytics (${analyticsUrl})`);
      });
      logger.info(`[reconcile] deleted orphan source ${sourceId} from videostream-analytics (${analyticsUrl})`);
      deleted++;
    }
  }

  logger.info(`[reconcile] complete: ${offlined} marked offline, ${deleted} orphans deleted`);
}

main().catch((err) => {
  logger.error(`MCP Server failed to start: ${err}`);
  process.exit(1);
});
