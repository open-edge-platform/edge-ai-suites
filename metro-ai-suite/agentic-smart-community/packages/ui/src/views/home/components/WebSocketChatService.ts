// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
export type ConnectionStatus = "disconnected" | "connecting" | "connected";

const CONNECT_FAILED_CLOSE_CODE = 4008;
const CONNECT_DELAY_MS = 750;
const HISTORY_LIMIT = 200;
const OPENCLAW_GATEWAY_PROTOCOL = 4;
const CONTROL_UI_OPERATOR_ROLE = "operator";
const CONTROL_UI_OPERATOR_SCOPES = [
  "operator.admin",
  "operator.read",
  "operator.write",
  "operator.approvals",
  "operator.pairing",
] as const;
const TERMINAL_CHAT_STATES = new Set([
  "completed",
  "complete",
  "done",
  "error",
  "aborted",
  "cancelled",
  "failed",
]);

type GenericRecord = Record<string, any>;
type ChatStreamKind = "assistant" | "tool";
export type ChatMessageKind =
  | "user"
  | "assistant-text"
  | "tool-result"
  | "assistant-tool-call"
  | "assistant-agent-run";

export interface ChatAgentSummary {
  id: string;
  displayName: string;
  description: string;
}

export interface ChatSessionSummary {
  key: string;
  agentId: string;
  displayName: string;
  status: string;
  updatedAt: number;
  modelProvider: string;
  model: string;
}

export interface ChatSessionGroup {
  agentId: string;
  displayName: string;
  description: string;
  sessions: ChatSessionSummary[];
}

export interface ChatAgentSegment {
  id: string;
  stream: ChatStreamKind;
  title: string;
  subtitle: string;
  content: string;
  isComplete: boolean;
}

export interface ChatAgentRun {
  id: string;
  hasTool: boolean;
  isComplete: boolean;
  segments: ChatAgentSegment[];
}

export interface ChatMessageBlock {
  id: string;
  kind: "text" | "tool-call" | "tool-result" | "thinking";
  content: string;
  title: string;
  subtitle: string;
  showToolIcon: boolean;
  collapsible: boolean;
  startsCollapsed: boolean;
}

export interface ChatMessageView {
  id: string;
  role: "user" | "assistant" | "toolResult";
  messageKind: ChatMessageKind;
  content: string;
  timestamp?: number;
  model?: string;
  isCompleted: boolean;
  title: string;
  subtitle: string;
  showToolIcon: boolean;
  collapsible: boolean;
  startsCollapsed: boolean;
  contentBlocks?: ChatMessageBlock[];
  agents: ChatAgentRun[];
}

interface WebSocketChatServiceOptions {
  url: string;
  authToken: string;
  onMessagesChange: (messages: ChatMessageView[]) => void;
  onSessionsChange?: (
    sessions: ChatSessionSummary[],
    sessionGroups: ChatSessionGroup[],
    selectedSessionKey: string,
  ) => void;
  onHistoryLoadingChange?: (loading: boolean) => void;
  onStreamingChange?: (streaming: boolean) => void;
  onError?: (message: string) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
}

interface PendingRequest {
  resolve: any;
  reject: (error: Error) => void;
}

interface GatewayErrorShape {
  code?: string;
  message?: string;
  details?: unknown;
}

class GatewayRequestError extends Error {
  gatewayCode?: string;
  details?: unknown;

  constructor(error: GatewayErrorShape) {
    super(error.message || "request failed");
    this.name = "GatewayRequestError";
    this.gatewayCode = error.code;
    this.details = error.details;
  }
}

export class WebSocketChatService {
  private socket: WebSocket | null = null;
  private isHandshakeComplete = false;
  private isSessionsSubscribed = false;
  private shouldRefreshOnConnect = false;
  private awaitingResponse = false;
  private connectSent = false;
  private connectTimer: number | null = null;
  private pending = new Map<string, PendingRequest>();
  private messages: ChatMessageView[] = [];
  private agents: ChatAgentSummary[] = [];
  private sessions: ChatSessionSummary[] = [];
  private sessionGroups: ChatSessionGroup[] = [];
  private selectedSessionKey = "";
  private pendingQuestion = "";
  private isLoadingCatalog = false;
  private isLoadingHistory = false;
  private currentAssistantMessageId: string | null = null;
  private currentAgentRunId: string | null = null;
  private currentToolSegmentId: string | null = null;

  constructor(private readonly options: WebSocketChatServiceOptions) {}

  connect() {
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) {
      return;
    }

    this.setStatus("connecting");
    const socket = new WebSocket(this.options.url);
    this.socket = socket;

    socket.onopen = () => {
      this.queueConnect();
    };

    socket.onmessage = async (event) => {
      const data =
        typeof event.data === "string" ? event.data : await event.data.text();
      this.handleMessage(data);
    };

    socket.onerror = () => {
      this.options.onError?.("WebSocket error");
    };

    socket.onclose = (event) => {
      this.clearConnectTimer();
      this.flushPending(new Error("socket closed"));
      this.setStatus("disconnected");
      this.resetConnectionState();

      if (this.awaitingResponse) {
        if (event.reason) {
          this.options.onError?.(event.reason);
        }
        this.finishResponse();
      }

      if (this.socket === socket) {
        this.socket = null;
      }
    };
  }

  disconnect() {
    this.clearConnectTimer();
    this.socket?.close();
    this.socket = null;
    this.resetConnectionState();
    this.flushPending(new Error("socket closed"));
  }

  cancel() {
    this.pendingQuestion = "";
    this.awaitingResponse = false;
    this.markActiveAssistantComplete();
    this.publishMessages();
    this.options.onStreamingChange?.(false);
    this.disconnect();
  }

  sendChat(question: string) {
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion) {
      return Promise.resolve("");
    }

    const selectedSessionKey = this.getSelectedSessionKey();

    this.pendingQuestion = normalizedQuestion;

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.connect();
      return Promise.resolve("");
    }

    if (
      !this.isHandshakeComplete ||
      !selectedSessionKey ||
      this.isLoadingHistory
    ) {
      return Promise.resolve("");
    }

    return this.dispatchPendingQuestion();
  }

  private async createNewSession(command: string) {
    const selectedSessionKey = this.getSelectedSessionKey();

    if (!selectedSessionKey) {
      return "";
    }

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.connect();
      return "";
    }

    if (
      !this.isHandshakeComplete ||
      this.isLoadingHistory ||
      this.awaitingResponse
    ) {
      return "";
    }

    const currentSessionKey = selectedSessionKey;
    const currentAgentId = this.extractAgentIdFromSessionKey(currentSessionKey);
    const previousSessionKeys = new Set(
      this.sessions.map((session) => session.key),
    );
    this.appendOutgoingUserMessage(command);

    try {
      const payload = (await this.request("chat.send", {
        sessionKey: currentSessionKey,
        message: command,
        deliver: false,
        idempotencyKey: this.makeId(),
      })) as GenericRecord;

      await this.loadCatalog();

      return (
        this.resolveCreatedSessionKey(payload) ||
        this.findNewestSessionKey(
          previousSessionKeys,
          currentAgentId,
          currentSessionKey,
        ) ||
        currentSessionKey
      );
    } catch (error) {
      this.options.onError?.(this.getErrorMessage(error));
      return "";
    }
  }

  selectSession(sessionKey: string) {
    if (!sessionKey || sessionKey === this.selectedSessionKey) {
      return;
    }

    this.selectedSessionKey = sessionKey;
    this.publishSessions();

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.connect();
      return;
    }

    if (!this.isHandshakeComplete) {
      return;
    }

    void this.loadHistory(sessionKey);
  }

  async refreshHistory() {
    const selectedSessionKey = this.getSelectedSessionKey();

    if (this.awaitingResponse) {
      return;
    }

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.shouldRefreshOnConnect = true;
      this.connect();
      return;
    }

    if (!this.isHandshakeComplete) {
      this.shouldRefreshOnConnect = true;
      return;
    }

    this.shouldRefreshOnConnect = false;
    if (!selectedSessionKey) {
      return;
    }

    await this.loadHistory(selectedSessionKey);
  }

  private request(method: string, params: Record<string, unknown>) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("gateway not connected"));
    }

    const id = this.makeId();
    const frame = {
      type: "req",
      id,
      method,
      params,
    };

    const promise = new Promise<any>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
    });

    this.socket.send(JSON.stringify(frame));
    return promise;
  }

  private async sendConnectRequest() {
    if (this.connectSent) {
      return;
    }

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }

    this.connectSent = true;
    this.clearConnectTimer();

    try {
      await this.request("connect", this.buildConnectParams());
      this.markHandshakeComplete();
    } catch (error) {
      this.options.onError?.(this.getErrorMessage(error));
      this.socket?.close(CONNECT_FAILED_CLOSE_CODE, "connect failed");
    }
  }

  private async loadCatalog() {
    if (this.isLoadingCatalog) {
      return;
    }

    this.isLoadingCatalog = true;

    try {
      await this.ensureSessionsSubscribed();

      const agentsPayload = (await this.request(
        "agents.list",
        {},
      )) as GenericRecord;
      this.agents = this.normalizeAgents(agentsPayload);

      const sessionsPayload = (await this.request("sessions.list", {
        includeGlobal: true,
        includeUnknown: true,
      })) as GenericRecord;
      this.sessions = this.normalizeSessions(sessionsPayload);
      this.sessionGroups = this.buildSessionGroups(this.agents, this.sessions);
      this.publishSessions();
    } catch (error) {
      this.options.onError?.(this.getErrorMessage(error));
    } finally {
      this.isLoadingCatalog = false;
    }
  }

  private async loadHistory(sessionKey: string) {
    if (!sessionKey) {
      return;
    }

    this.setHistoryLoading(true);

    try {
      const payload = (await this.request("chat.history", {
        sessionKey,
        limit: HISTORY_LIMIT,
      })) as GenericRecord;

      if (this.getSelectedSessionKey() !== sessionKey) {
        return;
      }

      const rawMessages = Array.isArray(payload?.messages)
        ? payload.messages
        : [];
      this.messages = this.normalizeHistoryMessages(rawMessages);
      this.resetStreamingPointers();
      this.publishMessages();

      if (this.pendingQuestion) {
        void this.dispatchPendingQuestion();
      }
    } catch (error) {
      this.options.onError?.(this.getErrorMessage(error));
      this.messages = [];
      this.publishMessages();
    } finally {
      if (this.getSelectedSessionKey() === sessionKey) {
        this.setHistoryLoading(false);
      }
    }
  }

  private async dispatchPendingQuestion() {
    const selectedSessionKey = this.getSelectedSessionKey();

    if (!this.pendingQuestion || this.awaitingResponse || !selectedSessionKey) {
      return "";
    }

    const question = this.pendingQuestion;
    this.pendingQuestion = "";
    const responseSessionKey = selectedSessionKey;

    if (question === "/new") {
      return this.createNewSession(question);
    }

    this.awaitingResponse = true;
    this.options.onStreamingChange?.(true);
    this.appendOutgoingQuestion(question);

    try {
      await this.request("chat.send", {
        sessionKey: responseSessionKey,
        message: question,
        deliver: false,
        idempotencyKey: this.makeId(),
      });
      return "";
    } catch (error) {
      this.options.onError?.(this.getErrorMessage(error));
      this.finishResponse();
      return "";
    }
  }

  private queueConnect() {
    this.connectSent = false;
    this.clearConnectTimer();

    this.connectTimer = window.setTimeout(() => {
      void this.sendConnectRequest();
    }, CONNECT_DELAY_MS);
  }

  private clearConnectTimer() {
    if (this.connectTimer === null) {
      return;
    }

    window.clearTimeout(this.connectTimer);
    this.connectTimer = null;
  }

  private resetConnectionState() {
    this.isHandshakeComplete = false;
    this.isSessionsSubscribed = false;
    this.connectSent = false;
  }

  private async ensureSessionsSubscribed() {
    if (this.isSessionsSubscribed) {
      return;
    }

    await this.request("sessions.subscribe", {});
    this.isSessionsSubscribed = true;
  }

  private resetStreamingPointers() {
    this.currentAssistantMessageId = null;
    this.currentAgentRunId = null;
    this.currentToolSegmentId = null;
  }

  private buildConnectParams() {
    const token = this.options.authToken.trim();

    return {
      minProtocol: OPENCLAW_GATEWAY_PROTOCOL,
      maxProtocol: OPENCLAW_GATEWAY_PROTOCOL,
      client: {
        id: "openclaw-control-ui",
        version: "control-ui",
        platform: navigator.platform || "web",
        mode: "webchat",
      },
      role: CONTROL_UI_OPERATOR_ROLE,
      scopes: [...CONTROL_UI_OPERATOR_SCOPES],
      caps: ["tool-events"],
      auth: token ? { token } : undefined,
      userAgent: navigator.userAgent,
      locale: navigator.language,
    };
  }

  private setStatus(status: ConnectionStatus) {
    this.options.onStatusChange?.(status);
  }

  private setHistoryLoading(loading: boolean) {
    this.isLoadingHistory = loading;
    this.options.onHistoryLoadingChange?.(loading);
  }

  private publishSessions() {
    this.options.onSessionsChange?.(
      [...this.sessions],
      [...this.sessionGroups],
      this.getSelectedSessionKey(),
    );
  }

  private getRouteSessionKey() {
    if (typeof window === "undefined") {
      return "";
    }

    return new URLSearchParams(window.location.search).get("session") || "";
  }

  private getSelectedSessionKey() {
    const routeSessionKey = this.getRouteSessionKey();
    if (routeSessionKey && routeSessionKey !== this.selectedSessionKey) {
      this.selectedSessionKey = routeSessionKey;
    }

    return routeSessionKey || this.selectedSessionKey;
  }

  private publishMessages() {
    this.options.onMessagesChange(
      this.messages.map((message) => ({
        ...message,
        agents: message.agents.map((agent) => ({
          ...agent,
          segments: agent.segments.map((segment) => ({ ...segment })),
        })),
      })),
    );
  }

  private handleMessage(raw: string) {
    const messages = this.parseIncomingMessages(raw);

    if (messages.length === 0) {
      console.warn("parse error:", raw);
      return;
    }

    for (const msg of messages) {
      if (msg.type === "event") {
        this.handleEventMessage(msg);
        continue;
      }

      if (msg.type === "res") {
        this.handleResponseMessage(msg);
        continue;
      }

      if (msg.type === "error") {
        this.options.onError?.(msg.message || "Unknown error");
        this.finishResponse();
      }
    }
  }

  private parseIncomingMessages(raw: string) {
    const input = raw.trim();
    if (!input) {
      return [] as GenericRecord[];
    }

    try {
      return [JSON.parse(input) as GenericRecord];
    } catch (_error) {
      const messages: GenericRecord[] = [];
      let depth = 0;
      let startIndex = -1;
      let inString = false;
      let escaped = false;

      for (let index = 0; index < input.length; index += 1) {
        const char = input[index];

        if (inString) {
          if (escaped) {
            escaped = false;
            continue;
          }

          if (char === "\\") {
            escaped = true;
            continue;
          }

          if (char === '"') {
            inString = false;
          }

          continue;
        }

        if (char === '"') {
          inString = true;
          continue;
        }

        if (char === "{") {
          if (depth === 0) {
            startIndex = index;
          }
          depth += 1;
          continue;
        }

        if (char !== "}") {
          continue;
        }

        depth -= 1;
        if (depth !== 0 || startIndex === -1) {
          continue;
        }

        const chunk = input.slice(startIndex, index + 1);
        try {
          messages.push(JSON.parse(chunk) as GenericRecord);
        } catch (_chunkError) {
          console.warn("parse chunk error:", chunk);
        }
        startIndex = -1;
      }

      return messages;
    }
  }

  private handleEventMessage(msg: GenericRecord) {
    const eventName = this.resolveString(msg.event);
    const payload = this.toRecord(msg.payload) || msg;

    if (eventName === "connect.challenge") {
      void this.sendConnectRequest();
      return;
    }

    if (eventName === "connect.ok" || payload.type === "hello-ok") {
      this.markHandshakeComplete();
      return;
    }

    if (eventName === "chat.done") {
      this.finishResponse();
      return;
    }

    if (eventName === "agent") {
      this.handleAgentEvent(payload);
      return;
    }

    if (eventName === "chat") {
      this.handleChatEvent(payload);
      return;
    }

    if (eventName === "session.tool") {
      this.handleSessionToolEvent(payload);
      return;
    }
  }

  private handleResponseMessage(msg: GenericRecord) {
    const requestId = this.resolveString(msg.id);
    const pendingRequest = requestId ? this.pending.get(requestId) : undefined;

    if (pendingRequest) {
      this.pending.delete(requestId);
      if (msg.ok) {
        pendingRequest.resolve(msg.payload);
      } else {
        pendingRequest.reject(
          new GatewayRequestError({
            code: msg.error?.code,
            message: msg.error?.message,
            details: msg.error?.details,
          }),
        );
      }
      return;
    }

    if (msg.ok === false) {
      this.options.onError?.(msg.error?.message || "request failed");
      this.finishResponse();
      return;
    }

    if (msg.payload?.type === "hello-ok") {
      this.markHandshakeComplete();
    }
  }

  private handleChatEvent(payload: GenericRecord) {
    if (!this.shouldHandlePayloadForSelectedSession(payload)) {
      return;
    }

    const data = this.toRecord(payload.data) || payload;
    const text = this.extractTextFromUnknown(data.text ?? payload.text);

    if (text.trim()) {
      this.appendPlainAssistantText(text);
    }

    const state = this.resolveString(payload.state || data.state).toLowerCase();
    if (state === "final") {
      this.finishResponse();
      void this.reloadCatalogAndHistory();
      return;
    }

    if (TERMINAL_CHAT_STATES.has(state)) {
      this.finishResponse();
    }
  }

  private handleAgentEvent(payload: GenericRecord) {
    if (!this.shouldHandlePayloadForSelectedSession(payload)) {
      return;
    }

    const data = this.toRecord(payload.data) || {};
    const stream =
      this.resolveStreamKind(data) || this.resolveStreamKind(payload);
    const phase = this.resolveString(data.phase || payload.phase).toLowerCase();
    const state = this.resolveString(payload.state || data.state).toLowerCase();
    const text = this.extractTextFromUnknown(data.text ?? payload.text);

    if (payload.stream === "lifecycle") {
      if (phase === "start") {
        this.beginAgentRun();
        this.publishMessages();
        return;
      }

      if (phase === "end") {
        this.completeCurrentAgentRun();
        this.discardCurrentAgentRunIfEmpty();
      }

      if (phase === "error") {
        const errorMessage =
          this.resolveString(data.error) || this.resolveString(payload.error);
        this.options.onError?.(errorMessage);
        this.discardCurrentAgentRunIfEmpty();
      }

      if (phase === "error" || TERMINAL_CHAT_STATES.has(state)) {
        this.finishResponse();
      }

      this.publishMessages();
      return;
    }

    if (!stream) {
      if (text.trim()) {
        this.appendPlainAssistantText(text);
      }

      if (TERMINAL_CHAT_STATES.has(state)) {
        this.finishResponse();
      }

      return;
    }

    const agentRun = this.ensureCurrentAgentRun();
    if (!agentRun) {
      return;
    }

    if (stream === "assistant") {
      this.appendAssistantSegment(agentRun, text, phase);
    }

    if (stream === "tool") {
      agentRun.hasTool = true;
      this.appendToolSegment(agentRun, data, phase, text);
    }

    if (TERMINAL_CHAT_STATES.has(state)) {
      this.finishResponse();
      return;
    }

    this.publishMessages();
  }
  private handleSessionToolEvent(payload: GenericRecord) {
    if (!this.shouldHandlePayloadForSelectedSession(payload)) {
      return;
    }

    const data = this.toRecord(payload.data) || payload;
    const phase = this.resolveString(data.phase || payload.phase).toLowerCase();
    const state = this.resolveString(payload.state || data.state).toLowerCase();
    const text = this.extractTextFromUnknown(data.text ?? payload.text);
    const agentRun = this.ensureCurrentAgentRun();
    if (!agentRun) {
      return;
    }

    agentRun.hasTool = true;
    this.appendToolSegment(agentRun, data, phase, text);

    if (TERMINAL_CHAT_STATES.has(state)) {
      this.completeCurrentAgentRun();
      this.finishResponse();
      return;
    }

    this.publishMessages();
  }
  private normalizeAgents(payload: GenericRecord | null | undefined) {
    const rawAgents = this.resolveCollection(payload, [
      "agents",
      "items",
      "results",
      "data",
      "list",
      "entries",
    ]);

    return rawAgents
      .map((agent) => {
        const record = this.toRecord(agent);
        if (!record) {
          return null;
        }

        const id =
          this.resolveString(record.id) ||
          this.resolveString(record.agentId) ||
          this.resolveString(record.key);
        if (!id) {
          return null;
        }

        return {
          id,
          displayName:
            this.resolveString(record.displayName) ||
            this.resolveString(record.name) ||
            this.resolveString(record.label) ||
            id,
          description:
            this.resolveString(record.description) ||
            this.resolveString(record.prompt) ||
            "",
        } satisfies ChatAgentSummary;
      })
      .filter(Boolean) as ChatAgentSummary[];
  }

  private normalizeSessions(payload: GenericRecord | null | undefined) {
    const rawSessions = this.resolveCollection(payload, [
      "sessions",
      "items",
      "results",
      "data",
      "list",
      "entries",
    ]);

    return rawSessions
      .map((session) => {
        const record = this.toRecord(session);
        if (!record) {
          return null;
        }

        const key = this.resolveString(record.key);
        if (!key) {
          return null;
        }

        return {
          key,
          agentId: this.extractAgentIdFromSessionKey(key),
          displayName:
            this.resolveString(record.displayName) ||
            this.resolveString(record.label) ||
            key,
          status: this.resolveString(record.status) || "unknown",
          updatedAt: this.resolveNumber(record.updatedAt),
          modelProvider: this.resolveString(record.modelProvider),
          model: this.resolveString(record.model),
        } satisfies ChatSessionSummary;
      })
      .filter(Boolean) as ChatSessionSummary[];
  }

  private resolveCreatedSessionKey(payload: GenericRecord | null | undefined) {
    return this.resolvePayloadSessionKey(payload);
  }

  private shouldHandlePayloadForSelectedSession(
    payload: GenericRecord | null | undefined,
  ) {
    const selectedSessionKey = this.getSelectedSessionKey();
    const payloadSessionKey = this.resolvePayloadSessionKey(payload);

    return Boolean(
      selectedSessionKey &&
      payloadSessionKey &&
      payloadSessionKey === selectedSessionKey,
    );
  }

  private resolvePayloadSessionKey(payload: GenericRecord | null | undefined) {
    const directSessionKey = this.resolveString(payload?.sessionKey);
    if (directSessionKey) {
      return directSessionKey;
    }

    const sessionRecord = this.toRecord(payload?.session);
    const nestedSessionKey = this.resolveString(sessionRecord?.key);
    if (nestedSessionKey) {
      return nestedSessionKey;
    }

    const dataRecord = this.toRecord(payload?.data);
    const dataSessionKey = this.resolveString(
      dataRecord?.sessionKey || this.toRecord(dataRecord?.session)?.key,
    );
    if (dataSessionKey) {
      return dataSessionKey;
    }

    return "";
  }

  private findNewestSessionKey(
    previousSessionKeys: Set<string>,
    agentId: string,
    fallbackSessionKey: string,
  ) {
    const sameAgentSessions = this.sessions
      .filter((session) => session.agentId === agentId)
      .sort((a, b) => b.updatedAt - a.updatedAt);

    const newSession = sameAgentSessions.find(
      (session) => !previousSessionKeys.has(session.key),
    );
    if (newSession?.key) {
      return newSession.key;
    }

    return sameAgentSessions[0]?.key || fallbackSessionKey;
  }

  private buildSessionGroups(
    agents: ChatAgentSummary[],
    sessions: ChatSessionSummary[],
  ) {
    const agentMap = new Map(agents.map((agent) => [agent.id, agent]));
    const grouped = new Map<string, ChatSessionSummary[]>();

    sessions.forEach((session) => {
      const nextSessions = grouped.get(session.agentId) || [];
      nextSessions.push(session);
      grouped.set(session.agentId, nextSessions);
    });

    return [...grouped.entries()]
      .map(([agentId, groupedSessions]) => {
        const agent = agentMap.get(agentId);

        return {
          agentId,
          displayName: agent?.displayName || agentId || "Unknown agent",
          description: agent?.description || "",
          sessions: [...groupedSessions].sort(
            (a, b) => b.updatedAt - a.updatedAt,
          ),
        } satisfies ChatSessionGroup;
      })
      .sort((a, b) => a.displayName.localeCompare(b.displayName));
  }

  private normalizeHistoryMessages(rawMessages: unknown[]) {
    return rawMessages
      .map((message) => this.normalizeHistoryMessage(message))
      .filter(Boolean) as ChatMessageView[];
  }

  private normalizeHistoryMessage(rawMessage: unknown) {
    const record = this.toRecord(rawMessage);
    if (!record) {
      return null;
    }

    const timestamp = this.resolveNumber(record.timestamp);
    const model = this.resolveString(record.model);

    const role = this.resolveString(record.role).toLowerCase();

    if (role === "user") {
      return this.buildHistoryMessage({
        role: "user",
        messageKind: "user",
        content: this.extractTextFromUnknown(
          record.content ?? record.message ?? record,
        ),
        timestamp,
      });
    }

    if (role === "toolresult") {
      const block = this.buildContentBlock({
        kind: "tool-result",
        content: this.resolveToolResultDisplayText(record),
        title: "Tool output",
        subtitle:
          this.resolveString(record.toolName) ||
          this.resolveString(record.name) ||
          "",
        showToolIcon: true,
        collapsible: true,
        startsCollapsed: true,
      });

      return this.buildHistoryMessage({
        role: "toolResult",
        messageKind: "tool-result",
        content: block.content,
        timestamp,
        subtitle: block.subtitle,
        showToolIcon: block.showToolIcon,
        collapsible: block.collapsible,
        startsCollapsed: block.startsCollapsed,
        contentBlocks: [block],
      });
    }

    if (role === "assistant") {
      if (Array.isArray(record.content)) {
        if (record.content.length === 0) {
          return null;
        }
        const contentBlocks = this.normalizeAssistantContentBlocks(
          record.content,
        );
        if (!contentBlocks.length) {
          return null;
        }

        const textContent = contentBlocks
          .filter((block) => block.kind === "text")
          .map((block) => block.content)
          .join("\n\n");
        const hasToolCallBlock = contentBlocks.some(
          (block) => block.kind === "tool-call",
        );

        return this.buildHistoryMessage({
          role: "assistant",
          messageKind: hasToolCallBlock
            ? "assistant-tool-call"
            : "assistant-text",
          content: textContent,
          timestamp,
          model,
          contentBlocks,
        });
      }

      const contentRecord = this.toRecord(record.content);
      const contentType = this.resolveString(contentRecord?.type).toLowerCase();

      if (contentType === "toolcall") {
        const toolCallContent = this.resolveToolCallDisplayText(contentRecord);
        const block = this.buildContentBlock({
          kind: "tool-call",
          content: toolCallContent,
          title: "Tool",
          subtitle: this.resolveToolCallSubtitle(contentRecord),
          showToolIcon: true,
          collapsible: true,
          startsCollapsed: true,
        });

        return this.buildHistoryMessage({
          role: "assistant",
          messageKind: "assistant-tool-call",
          content: block.content,
          timestamp,
          model,
          subtitle: block.subtitle,
          showToolIcon: block.showToolIcon,
          collapsible: block.collapsible,
          startsCollapsed: block.startsCollapsed,
          contentBlocks: [block],
        });
      }

      if (contentType === "text") {
        const block = this.buildContentBlock({
          kind: "text",
          content: this.extractTextFromUnknown(
            contentRecord?.text ?? contentRecord?.value ?? contentRecord,
          ),
          title: "",
          subtitle: "",
          showToolIcon: false,
          collapsible: false,
          startsCollapsed: false,
        });

        return this.buildHistoryMessage({
          role: "assistant",
          messageKind: "assistant-text",
          content: block.content,
          timestamp,
          model,
          contentBlocks: [block],
        });
      }

      const fallbackBlock = this.buildContentBlock({
        kind: "text",
        content: this.extractTextFromUnknown(
          record.content ?? record.message ?? record,
        ),
        title: "",
        subtitle: "",
        showToolIcon: false,
        collapsible: false,
        startsCollapsed: false,
      });

      return this.buildHistoryMessage({
        role: "assistant",
        messageKind: "assistant-text",
        content: fallbackBlock.content,
        timestamp,
        model,
        contentBlocks: [fallbackBlock],
      });
    }

    return null;
  }

  private buildHistoryMessage(input: {
    role: ChatMessageView["role"];
    messageKind: ChatMessageView["messageKind"];
    content: string;
    timestamp?: number;
    model?: string;
    subtitle?: string;
    showToolIcon?: boolean;
    collapsible?: boolean;
    startsCollapsed?: boolean;
    contentBlocks?: ChatMessageBlock[];
  }) {
    return {
      id: this.makeId(),
      role: input.role,
      messageKind: input.messageKind,
      content: input.content || "",
      timestamp: input.timestamp,
      model: input.model || "",
      isCompleted: true,
      title: input.showToolIcon ? "Tool output" : "",
      subtitle: input.subtitle || "",
      showToolIcon: Boolean(input.showToolIcon),
      collapsible: Boolean(input.collapsible),
      startsCollapsed: Boolean(input.startsCollapsed),
      contentBlocks: input.contentBlocks || [],
      agents: [],
    } satisfies ChatMessageView;
  }

  private normalizeAssistantContentBlocks(rawContentList: unknown[]) {
    return rawContentList
      .map((item) => {
        const record = this.toRecord(item);
        if (!record) {
          const fallbackContent = this.extractTextFromUnknown(item);
          if (!fallbackContent) {
            return null;
          }

          return this.buildContentBlock({
            kind: "text",
            content: fallbackContent,
            title: "",
            subtitle: "",
            showToolIcon: false,
            collapsible: false,
            startsCollapsed: false,
          });
        }

        const type = this.resolveString(record.type).toLowerCase();
        if (type === "text") {
          return this.buildContentBlock({
            kind: "text",
            content: this.extractTextFromUnknown(
              record.text ?? record.value ?? record.content ?? record,
            ),
            title: "",
            subtitle: "",
            showToolIcon: false,
            collapsible: false,
            startsCollapsed: false,
          });
        }

        if (type === "toolcall" || type === "tooluse") {
          const toolCallContent = this.resolveToolCallDisplayText(record);
          return this.buildContentBlock({
            kind: "tool-call",
            content: toolCallContent,
            title: "Tool",
            subtitle: this.resolveToolCallSubtitle(record),
            showToolIcon: true,
            collapsible: true,
            startsCollapsed: true,
          });
        }

        if (type === "thinking") {
          const thinkingContent = this.extractTextFromUnknown(
            record.thinking ?? record.text ?? record.value ?? record.content,
          );
          if (!thinkingContent) {
            return null;
          }

          return this.buildContentBlock({
            kind: "thinking",
            content: thinkingContent,
            title: "Thinking",
            subtitle: "",
            showToolIcon: false,
            collapsible: true,
            startsCollapsed: true,
          });
        }

        const fallbackContent = this.extractTextFromUnknown(record);
        if (!fallbackContent) {
          return null;
        }

        return this.buildContentBlock({
          kind: "text",
          content: fallbackContent,
          title: "",
          subtitle: "",
          showToolIcon: false,
          collapsible: false,
          startsCollapsed: false,
        });
      })
      .filter(Boolean) as ChatMessageBlock[];
  }

  private buildContentBlock(input: {
    kind: ChatMessageBlock["kind"];
    content: string;
    title: string;
    subtitle: string;
    showToolIcon: boolean;
    collapsible: boolean;
    startsCollapsed: boolean;
  }) {
    return {
      id: this.makeId(),
      kind: input.kind,
      content: input.content || "",
      title: input.title,
      subtitle: input.subtitle,
      showToolIcon: input.showToolIcon,
      collapsible: input.collapsible,
      startsCollapsed: input.startsCollapsed,
    } satisfies ChatMessageBlock;
  }

  private extractAgentIdFromSessionKey(sessionKey: string) {
    const exactMatch = sessionKey.match(/(?:^|[:/])agent[:/]([^:/]+)/i);
    if (exactMatch?.[1]) {
      return exactMatch[1];
    }

    const segments = sessionKey.split(":");
    const agentIndex = segments.findIndex(
      (segment) => segment.toLowerCase() === "agent",
    );
    if (agentIndex >= 0 && segments[agentIndex + 1]) {
      return segments[agentIndex + 1];
    }

    return "ungrouped";
  }

  private appendOutgoingQuestion(question: string) {
    const userMessage = this.buildOutgoingUserMessage(question);

    const assistantMessage: ChatMessageView = {
      id: this.makeId(),
      role: "assistant",
      messageKind: "assistant-text",
      content: "",
      isCompleted: false,
      title: "",
      subtitle: "",
      showToolIcon: false,
      collapsible: false,
      startsCollapsed: false,
      contentBlocks: [],
      agents: [],
    };

    this.messages = [...this.messages, userMessage, assistantMessage];
    this.currentAssistantMessageId = assistantMessage.id;
    this.currentAgentRunId = null;
    this.publishMessages();
  }

  private appendOutgoingUserMessage(question: string) {
    this.messages = [...this.messages, this.buildOutgoingUserMessage(question)];
    this.publishMessages();
  }

  private buildOutgoingUserMessage(question: string) {
    return {
      id: this.makeId(),
      role: "user",
      messageKind: "user",
      content: question,
      isCompleted: true,
      title: "",
      subtitle: "",
      showToolIcon: false,
      collapsible: false,
      startsCollapsed: false,
      contentBlocks: [],
      agents: [],
    } satisfies ChatMessageView;
  }

  private appendPlainAssistantText(text: string) {
    const trimmedText = text.trim();
    if (!trimmedText) {
      return;
    }

    const assistantMessage = this.ensureStreamingAssistantMessage();
    if (!assistantMessage) {
      return;
    }

    assistantMessage.content = text;
    this.publishMessages();
  }

  private ensureStreamingAssistantMessage() {
    if (this.currentAssistantMessageId) {
      const currentMessage = this.messages.find(
        (message) => message.id === this.currentAssistantMessageId,
      );
      if (currentMessage) {
        return currentMessage;
      }
    }

    const lastMessage = this.messages[this.messages.length - 1];
    if (lastMessage?.role === "assistant" && !lastMessage.isCompleted) {
      this.currentAssistantMessageId = lastMessage.id;
      return lastMessage;
    }

    const assistantMessage: ChatMessageView = {
      id: this.makeId(),
      role: "assistant",
      messageKind: "assistant-text",
      content: "",
      isCompleted: false,
      title: "",
      subtitle: "",
      showToolIcon: false,
      collapsible: false,
      startsCollapsed: false,
      contentBlocks: [],
      agents: [],
    };
    this.messages = [...this.messages, assistantMessage];
    this.currentAssistantMessageId = assistantMessage.id;
    return assistantMessage;
  }

  private beginAgentRun() {
    const assistantMessage = this.ensureStreamingAssistantMessage();
    if (!assistantMessage) {
      return null;
    }

    assistantMessage.messageKind = "assistant-agent-run";
    assistantMessage.contentBlocks = [];
    const agentRun: ChatAgentRun = {
      id: this.makeId(),
      hasTool: false,
      isComplete: false,
      segments: [],
    };
    assistantMessage.agents.push(agentRun);
    this.currentAgentRunId = agentRun.id;
    this.currentToolSegmentId = null;
    return agentRun;
  }

  private ensureCurrentAgentRun() {
    const assistantMessage = this.ensureStreamingAssistantMessage();
    if (!assistantMessage) {
      return null;
    }

    assistantMessage.messageKind = "assistant-agent-run";

    if (this.currentAgentRunId) {
      const currentRun = assistantMessage.agents.find(
        (agent) => agent.id === this.currentAgentRunId,
      );
      if (currentRun) {
        return currentRun;
      }
    }

    const lastRun = assistantMessage.agents[assistantMessage.agents.length - 1];
    if (lastRun && !lastRun.isComplete) {
      this.currentAgentRunId = lastRun.id;
      return lastRun;
    }

    return this.beginAgentRun();
  }

  private completeCurrentAgentRun() {
    if (!this.currentAssistantMessageId || !this.currentAgentRunId) {
      return;
    }

    const assistantMessage = this.messages.find(
      (message) => message.id === this.currentAssistantMessageId,
    );
    const agentRun = assistantMessage?.agents.find(
      (agent) => agent.id === this.currentAgentRunId,
    );

    if (!agentRun) {
      this.currentAgentRunId = null;
      return;
    }

    agentRun.isComplete = true;
    agentRun.segments.forEach((segment) => {
      segment.isComplete = true;
    });
    this.currentAgentRunId = null;
    this.currentToolSegmentId = null;
  }

  private discardCurrentAgentRunIfEmpty() {
    const currentAssistantMessageId = this.currentAssistantMessageId;
    const currentAgentRunId = this.currentAgentRunId;

    if (!currentAssistantMessageId || !currentAgentRunId) {
      return;
    }

    const assistantMessage = this.messages.find(
      (message) => message.id === currentAssistantMessageId,
    );
    if (!assistantMessage || assistantMessage.role !== "assistant") {
      this.currentAgentRunId = null;
      this.currentToolSegmentId = null;
      return;
    }

    assistantMessage.agents = assistantMessage.agents.filter((agent) => {
      if (agent.id !== currentAgentRunId) {
        return true;
      }

      return agent.segments.length > 0;
    });

    if (assistantMessage.agents.length === 0) {
      assistantMessage.messageKind = "assistant-text";
    }

    const hasVisibleContent =
      assistantMessage.content.trim().length > 0 ||
      (assistantMessage.contentBlocks?.length || 0) > 0 ||
      assistantMessage.agents.length > 0;

    if (!hasVisibleContent && !assistantMessage.isCompleted) {
      this.messages = this.messages.filter(
        (message) => message.id !== currentAssistantMessageId,
      );
      this.currentAssistantMessageId = null;
    }

    this.currentAgentRunId = null;
    this.currentToolSegmentId = null;
  }

  private markActiveAssistantComplete() {
    const assistantMessage = this.currentAssistantMessageId
      ? this.messages.find(
          (message) => message.id === this.currentAssistantMessageId,
        )
      : this.messages[this.messages.length - 1];

    if (!assistantMessage || assistantMessage.role !== "assistant") {
      this.resetStreamingPointers();
      return;
    }

    this.completeCurrentAgentRun();
    assistantMessage.isCompleted = true;
    assistantMessage.agents.forEach((agent) => {
      agent.isComplete = true;
      agent.segments.forEach((segment) => {
        segment.isComplete = true;
      });
    });

    assistantMessage.agents = assistantMessage.agents.filter(
      (agent) => agent.segments.length > 0,
    );

    const hasVisibleContent =
      assistantMessage.content.trim().length > 0 ||
      (assistantMessage.contentBlocks?.length || 0) > 0 ||
      assistantMessage.agents.length > 0;

    if (!hasVisibleContent) {
      this.messages = this.messages.filter(
        (message) => message.id !== assistantMessage.id,
      );
      this.resetStreamingPointers();
      return;
    }

    if (assistantMessage.agents.length === 0) {
      assistantMessage.messageKind = "assistant-text";
    }

    this.resetStreamingPointers();
  }

  private markHandshakeComplete() {
    if (this.isHandshakeComplete) {
      return;
    }

    this.isHandshakeComplete = true;
    this.setStatus("connected");

    if (this.shouldRefreshOnConnect) {
      this.shouldRefreshOnConnect = false;
      const selectedSessionKey = this.getSelectedSessionKey();
      if (selectedSessionKey) {
        void this.loadHistory(selectedSessionKey);
        return;
      }

      void this.loadCatalog();
      return;
    }

    void this.loadCatalog();
  }

  private finishResponse() {
    if (!this.awaitingResponse) {
      return;
    }

    this.awaitingResponse = false;
    this.markActiveAssistantComplete();
    this.publishMessages();
    this.options.onStreamingChange?.(false);
  }

  private async reloadCatalogAndHistory() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }

    await this.loadCatalog();
    const selectedSessionKey = this.getSelectedSessionKey();
    if (selectedSessionKey) {
      await this.loadHistory(selectedSessionKey);
    }
  }

  private flushPending(error: Error) {
    for (const [, pendingRequest] of this.pending) {
      pendingRequest.reject(error);
    }

    this.pending.clear();
  }

  private getErrorMessage(error: unknown) {
    if (error instanceof Error && error.message) {
      return error.message;
    }

    return String(error);
  }

  private makeId() {
    if (
      typeof crypto !== "undefined" &&
      typeof crypto.randomUUID === "function"
    ) {
      return crypto.randomUUID();
    }

    return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }

  private toRecord(value: unknown) {
    return value && typeof value === "object" ? (value as GenericRecord) : null;
  }

  private appendAssistantSegment(
    agentRun: ChatAgentRun,
    text: string,
    phase: string,
  ) {
    if (text.trim()) {
      const existingSegment = [...agentRun.segments]
        .reverse()
        .find((segment) => segment.stream === "assistant");

      if (existingSegment && !existingSegment.isComplete) {
        existingSegment.content = text;
      } else {
        agentRun.segments.push({
          id: this.makeId(),
          stream: "assistant",
          title: "",
          subtitle: "",
          content: text,
          isComplete: false,
        });
      }
    }

    if (phase === "end") {
      const segment = [...agentRun.segments]
        .reverse()
        .find((item) => item.stream === "assistant" && !item.isComplete);
      if (segment) {
        segment.isComplete = true;
      }
    }
  }

  private appendToolSegment(
    agentRun: ChatAgentRun,
    data: GenericRecord,
    phase: string,
    text: string,
  ) {
    const nextTitle = this.resolveToolSegmentTitle(phase);
    const nextSubtitle = this.resolveToolSegmentSubtitle(data);
    const nextContent = this.resolveToolSegmentDisplayText(data, phase, text);

    if (phase === "start") {
      const segment: ChatAgentSegment = {
        id: this.makeId(),
        stream: "tool",
        title: nextTitle,
        subtitle: nextSubtitle,
        content: nextContent,
        isComplete: false,
      };
      agentRun.segments.push(segment);
      this.currentToolSegmentId = segment.id;
      return;
    }

    const segment = this.findCurrentToolSegment(agentRun);
    if (!segment) {
      const fallbackSegment: ChatAgentSegment = {
        id: this.makeId(),
        stream: "tool",
        title: nextTitle,
        subtitle: nextSubtitle,
        content: nextContent,
        isComplete: false,
      };
      agentRun.segments.push(fallbackSegment);
      this.currentToolSegmentId = fallbackSegment.id;
    }

    const activeSegment = this.findCurrentToolSegment(agentRun);
    if (!activeSegment) {
      return;
    }

    activeSegment.title = nextTitle || activeSegment.title;
    activeSegment.subtitle = nextSubtitle || activeSegment.subtitle;

    if (nextContent) {
      activeSegment.content = nextContent;
    }

    if (phase === "result") {
      activeSegment.isComplete = true;
      this.currentToolSegmentId = null;
      return;
    }

    if (phase === "end") {
      activeSegment.isComplete = true;
      this.currentToolSegmentId = null;
    }
  }

  private findCurrentToolSegment(agentRun: ChatAgentRun) {
    if (this.currentToolSegmentId) {
      const currentSegment = agentRun.segments.find(
        (segment) => segment.id === this.currentToolSegmentId,
      );
      if (currentSegment) {
        return currentSegment;
      }
    }

    return [...agentRun.segments]
      .reverse()
      .find((segment) => segment.stream === "tool" && !segment.isComplete);
  }

  private resolveToolSegmentTitle(phase: string) {
    return phase === "result" ? "Tool output" : "Tool";
  }

  private resolveToolSegmentSubtitle(data: GenericRecord) {
    return this.resolveString(data.name) || this.resolveString(data.toolName);
  }

  private resolveToolSegmentDisplayText(
    data: GenericRecord,
    phase: string,
    text: string,
  ) {
    if (phase === "result") {
      const resultRecord = this.toRecord(data.result);
      if (resultRecord) {
        const resultText = this.resolveToolResultDisplayText(resultRecord);
        if (resultText) {
          return resultText;
        }
      }

      const directResultText = this.resolveToolResultDisplayText(data);
      if (directResultText) {
        return directResultText;
      }

      if (text.trim()) {
        return text;
      }

      return this.formatToolPayloadAsJson(data.meta ?? data.result ?? data);
    }

    if (text.trim()) {
      return text;
    }

    return this.formatToolCallArguments(
      data.args ?? data.arguments ?? data.params ?? data.input,
    );
  }

  private resolveToolCallSubtitle(record: GenericRecord | null | undefined) {
    if (!record) {
      return "";
    }

    return (
      this.resolveString(record.name) || this.resolveString(record.toolName)
    );
  }

  private resolveToolCallDisplayText(record: GenericRecord | null | undefined) {
    if (!record) {
      return "";
    }

    return this.formatToolCallArguments(
      record.arguments ?? record.args ?? record.params ?? record.input,
    );
  }

  private formatToolCallArguments(value: unknown) {
    if (value === undefined) {
      return "";
    }

    return this.formatToolPayloadAsJson(value);
  }

  private resolveToolResultDisplayText(
    record: GenericRecord | null | undefined,
  ) {
    if (!record) {
      return "";
    }

    const preferredText = this.extractToolResultPreferredText(
      record.content ??
        this.toRecord(record.result)?.content ??
        this.toRecord(record.result)?.context ??
        record.context ??
        record.result,
    );
    if (preferredText) {
      return this.parseJsonText(preferredText);
    }

    return this.formatToolPayloadAsJson(
      record.content ?? record.result ?? record.output ?? record.message,
    );
  }

  private extractToolResultPreferredText(value: unknown): string {
    const textFromContent = this.extractTextFromContentCollection(value);
    if (textFromContent) {
      return textFromContent;
    }

    if (typeof value === "string") {
      return value;
    }

    if (Array.isArray(value)) {
      return value
        .map((item) => this.extractToolResultPreferredText(item))
        .filter(Boolean)
        .join("\n\n")
        .trim();
    }

    const record = this.toRecord(value);
    if (!record) {
      return "";
    }

    const directTextCandidates = [
      record["#sym:content"],
      record.text,
      record.content,
      record.context,
      record.result,
      record.value,
      record.message,
      record.output,
    ];

    for (const candidate of directTextCandidates) {
      const resolvedText = this.extractToolResultPreferredText(candidate);
      if (resolvedText) {
        return resolvedText;
      }
    }

    return "";
  }

  private extractTextFromContentCollection(value: unknown) {
    if (!Array.isArray(value)) {
      return "";
    }

    const textItems = value
      .map((item) => this.toRecord(item))
      .filter(Boolean)
      .filter((item) => this.resolveString(item?.type).toLowerCase() === "text")
      .map((item) => this.resolveString(item?.text))
      .filter(Boolean);

    return textItems.join("\n\n");
  }

  private resolveString(value: unknown) {
    return typeof value === "string" ? value : "";
  }

  private parseJsonText(value: string) {
    const trimmedValue = value.trim();
    if (!trimmedValue) {
      return value;
    }

    try {
      return this.formatToolPayloadAsJson(JSON.parse(trimmedValue));
    } catch {
      return value;
    }
  }

  private formatToolPayloadAsJson(value: unknown) {
    const normalizedValue = this.normalizeToolPayload(value);

    try {
      return JSON.stringify(normalizedValue, null, 2);
    } catch {
      return this.extractTextFromUnknown(value);
    }
  }

  private normalizeToolPayload(value: unknown): unknown {
    const record = this.toRecord(value);
    if (record) {
      const symbolContent = record["#sym:content"];
      if (symbolContent !== undefined) {
        const symbolRecord = this.toRecord(symbolContent);
        if (symbolRecord && typeof symbolRecord.text === "string") {
          return this.normalizeToolPayload(symbolRecord.text);
        }

        return this.normalizeToolPayload(symbolContent);
      }

      if (typeof record.text === "string") {
        return this.normalizeToolPayload(record.text);
      }

      if (typeof record.content === "string") {
        return this.normalizeToolPayload(record.content);
      }

      const contentRecord = this.toRecord(record.content);
      if (contentRecord && typeof contentRecord.text === "string") {
        return this.normalizeToolPayload(contentRecord.text);
      }

      return record;
    }

    if (typeof value === "string") {
      const trimmedValue = value.trim();
      if (!trimmedValue) {
        return "";
      }

      try {
        return JSON.parse(trimmedValue);
      } catch {
        return value;
      }
    }

    return value;
  }

  private resolveNumber(value: unknown) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }

    if (typeof value === "string") {
      const parsedValue = Number(value);
      if (Number.isFinite(parsedValue)) {
        return parsedValue;
      }

      const parsedTimestamp = Date.parse(value);
      if (Number.isFinite(parsedTimestamp)) {
        return parsedTimestamp;
      }
    }

    return 0;
  }

  private resolveCollection(
    payload: GenericRecord | null | undefined,
    keys: string[],
  ): unknown[] {
    if (Array.isArray(payload)) {
      return payload;
    }

    const record = this.toRecord(payload);
    if (!record) {
      return [];
    }

    for (const key of keys) {
      if (Array.isArray(record[key])) {
        return record[key];
      }
    }

    for (const value of Object.values(record)) {
      if (Array.isArray(value)) {
        return value;
      }
    }

    return [];
  }

  private resolveStreamKind(payload: GenericRecord): ChatStreamKind | null {
    const streamCandidates = [
      payload.stream,
      payload.channel,
      payload.kind,
      payload.type,
    ];

    for (const candidate of streamCandidates) {
      const normalized = this.resolveString(candidate).toLowerCase();
      if (
        normalized === "tool" ||
        normalized === "tool_call" ||
        normalized === "tool-call" ||
        normalized === "toolresult"
      ) {
        return "tool";
      }

      if (
        normalized === "assistant" ||
        normalized === "text" ||
        normalized === "message"
      ) {
        return "assistant";
      }
    }

    return null;
  }

  private extractTextFromUnknown(value: unknown): string {
    if (typeof value === "string") {
      return value;
    }

    if (typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }

    if (Array.isArray(value)) {
      return value
        .map((item) => this.extractTextFromUnknown(item))
        .join("\n")
        .trim();
    }

    const record = this.toRecord(value);
    if (!record) {
      return "";
    }

    const directCandidates = [
      record.text,
      record.value,
      record.prompt,
      record.output,
      record.input,
      record.content,
      record.message,
      record.result,
    ];

    for (const candidate of directCandidates) {
      if (typeof candidate === "string") {
        return candidate;
      }
    }

    if (record.prompt || record.arguments || record.params) {
      return this.extractTextFromUnknown(
        record.prompt ?? record.arguments?.prompt ?? record.params?.prompt,
      );
    }

    try {
      return JSON.stringify(record, null, 2);
    } catch {
      return "";
    }
  }
}
