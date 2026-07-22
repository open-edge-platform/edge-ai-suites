import type { AlertSink, AlertPayload, Logger } from "@smartbuilding-video/framework-adapter-sdk";
import type { PluginConfig } from "./config.js";
import type { SessionAppender } from "./inject-types.js";
import { formatAlert, formatSeparator } from "./format.js";

/**
 * Subset of OpenClaw's `api.runtime.subagent` we use: runs an ephemeral subagent whose reply is
 * delivered to `sessionKey` (only for the `deliver:true` channel path).
 */
export interface SubagentLike {
  run(params: {
    sessionKey: string;
    message: string;
    deliver?: boolean;
    extraSystemPrompt?: string;
    lane?: string;
    idempotencyKey?: string;
  }): Promise<{ runId: string }>;
}

// deliver:true still costs one LLM hop (the channel adapter runs an LLM); pin it to a verbatim
// relay so the raw alert passes through unrewritten.
const RELAY_PROMPT =
  "You are a message relay. Output the user's message verbatim — no rewriting, no additions, no questions.";

/**
 * OpenClaw AlertSink: routes each alert to its monitor's configured targets.
 *
 * `deliver` decides whether to ALSO push to an external channel, not which mechanism is used:
 * - `deliver:false` → inject the alert turn into the session (appendToSession), zero LLM.
 * - `deliver:true`  → channel-bound session (e.g. Feishu): `subagent.run` with a verbatim relay.
 *   That turn both delivers to the channel and records itself in the session, so we do NOT also
 *   appendToSession (would double-record).
 *
 * Idempotent per `alert.id`: appendToSession gets a stable idempotencyKey, and the deliver:true
 * path passes the same key so the gateway suppresses a duplicate run.
 */
export function createOpenClawSink(deps: {
  config: PluginConfig;
  logger: Logger;
  appendToSession: SessionAppender;
  subagent?: SubagentLike;
}): AlertSink {
  const { config, logger, appendToSession, subagent } = deps;

  return {
    async push({ monitorId, alert }: AlertPayload): Promise<void> {
      const targets = config.monitors[monitorId]?.alerts ?? [];
      if (targets.length === 0) {
        logger.warn(`[sb-alerts] no alert route configured for monitor=${monitorId} (alert id=${alert.id})`);
        return;
      }

      const separator = formatSeparator(alert);
      const body = formatAlert(alert);
      const idempotencyKey = `sb-alert:${monitorId}:${alert.id}`;

      await Promise.all(
        targets.map(async (t) => {
          if (t.deliver) {
            if (!subagent) {
              logger.error(
                `[sb-alerts] target ${t.sessionKey} needs deliver:true but api.runtime.subagent is unavailable — dropped alert id=${alert.id}`,
              );
              return;
            }
            try {
              const res = await subagent.run({
                sessionKey: t.sessionKey,
                message: body,
                deliver: true,
                lane: "alert",
                extraSystemPrompt: RELAY_PROMPT,
                idempotencyKey,
              });
              logger.info(`[sb-alerts] delivered alert id=${alert.id} → ${t.sessionKey} (runId=${res.runId})`);
            } catch (err) {
              logger.warn(`[sb-alerts] deliver failed alert id=${alert.id} → ${t.sessionKey}: ${err}`);
            }
            return;
          }

          const r = await appendToSession({
            agentId: t.agentId,
            sessionKey: t.sessionKey,
            separatorText: separator,
            assistantText: body,
            idempotencyKey,
            logger,
          });
          if (r.ok) {
            logger.info(`[sb-alerts] appended alert id=${alert.id} → ${t.sessionKey} (sid=${r.sessionId})`);
          } else {
            logger.warn(`[sb-alerts] append failed alert id=${alert.id} → ${t.sessionKey}: ${r.reason}`);
          }
        }),
      );
    },
  };
}
