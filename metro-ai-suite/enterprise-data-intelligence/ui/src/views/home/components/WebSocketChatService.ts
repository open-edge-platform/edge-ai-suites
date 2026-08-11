// Copyright (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

export type ConnectionStatus = "disconnected" | "connecting" | "connected";

const CONNECT_FAILED_CLOSE_CODE = 4008;
const CONNECT_DELAY_MS = 750;
const HISTORY_LIMIT = 200;
const MAIN_AGENT_SESSION_KEY = "agent:main:main";
const SUBAGENT_SESSION_KEY_PREFIX = "subagent";
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
type AssistantAgentLevel = "main" | "sub" | "none";
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
  agentLevel: Exclude<AssistantAgentLevel, "none">;
  title: string;
  hasTool: boolean;
  isComplete: boolean;
  segments: ChatAgentSegment[];
}

export interface ChatMessageBlock {
  id: string;
  kind: "text" | "tool-call" | "tool-result" | "thinking" | "error";
  content: string;
  title: string;
  subtitle: string;
  tag?: string;
  showToolIcon: boolean;
  collapsible: boolean;
  startsCollapsed: boolean;
}

export interface ChatMessageView {
  id: string;
  role: "user" | "assistant" | "toolResult";
  messageKind: ChatMessageKind;
  content: string;
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
  private activeAgentRunKeys = new Map<string, string>();
  private currentToolSegmentIds = new Map<string, string>();

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

    this.pendingQuestion = normalizedQuestion;

    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.connect();
      return Promise.resolve("");
    }

    if (
      !this.isHandshakeComplete ||
      !this.selectedSessionKey ||
      this.isLoadingHistory
    ) {
      return Promise.resolve("");
    }

    return this.dispatchPendingQuestion();
  }

  private async createNewSession(command: string) {
    if (!this.selectedSessionKey) {
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

    const currentSessionKey = this.selectedSessionKey;
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
    if (!sessionKey) {
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

      if (this.selectedSessionKey !== sessionKey) {
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
      if (this.selectedSessionKey === sessionKey) {
        this.setHistoryLoading(false);
      }
    }
  }

  private async dispatchPendingQuestion() {
    if (
      !this.pendingQuestion ||
      this.awaitingResponse ||
      !this.selectedSessionKey
    ) {
      return "";
    }

    const question = this.pendingQuestion;
    this.pendingQuestion = "";

    if (question === "/new") {
      return this.createNewSession(question);
    }

    this.awaitingResponse = true;
    this.options.onStreamingChange?.(true);
    this.appendOutgoingQuestion(question);

    try {
      await this.request("chat.send", {
        sessionKey: this.selectedSessionKey,
        message: question,
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

  private resetStreamingPointers() {
    this.currentAssistantMessageId = null;
    this.activeAgentRunKeys.clear();
    this.currentToolSegmentIds.clear();
  }
  private async ensureSessionsSubscribed() {
    if (this.isSessionsSubscribed) {
      return;
    }

    await this.request("sessions.subscribe", {});
    this.isSessionsSubscribed = true;
  }

  private buildConnectParams() {
    const token = this.options.authToken.trim();

    return {
      minProtocol: 3,
      maxProtocol: 3,
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
      this.selectedSessionKey,
    );
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

    if (eventName === "session.tool") {
      this.handleSessionToolEvent(payload);
      return;
    }

    if (eventName === "chat") {
      this.handleChatEvent(payload);
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
    const data = this.toRecord(payload.data) || payload;
    const text = this.extractTextFromUnknown(
      data.text ??
        data.message ??
        data.delta ??
        payload.text ??
        payload.message ??
        payload.delta ??
        data,
    );

    if (text.trim()) {
      this.appendPlainAssistantText(text);
    }

    const state = this.resolveString(payload.state || data.state).toLowerCase();
    if (state === "final") {
      this.finishResponse();
      void this.refreshCatalogAndHistory();
      return;
    }

    if (TERMINAL_CHAT_STATES.has(state)) {
      this.finishResponse();
    }
  }

  private handleAgentEvent(payload: GenericRecord) {
    const data = this.toRecord(payload.data) || {};
    const agentLevel = this.getAgentLevel(payload, data);
    const stream =
      this.resolveStreamKind(data) || this.resolveStreamKind(payload);
    const phase = this.resolveString(data.phase || payload.phase).toLowerCase();
    const state = this.resolveString(payload.state || data.state).toLowerCase();
    const errorText = this.extractTextFromUnknown(
      data.errorMessage ??
        data.error ??
        data.message ??
        payload.errorMessage ??
        payload.error ??
        payload.message,
    ).trim();
    const text = this.extractTextFromUnknown(
      data.text ??
        data.message ??
        data.content ??
        data.delta ??
        payload.delta ??
        payload.message ??
        payload.content ??
        payload.text,
    );

    if (payload.stream === "lifecycle") {
      if (agentLevel !== "none" && phase === "start") {
        this.beginAgentRun(agentLevel, payload, data);
      }

      if (agentLevel !== "none" && phase === "end") {
        this.completeAgentRun(agentLevel, payload, data);
      }

      if (phase === "error") {
        if (errorText) {
          this.appendAssistantErrorBlock(errorText);
        }

        if (agentLevel !== "none") {
          this.handleAgentRunError(agentLevel, payload, data);
        }

        this.finishResponse();
        this.publishMessages();
        return;
      }

      if (TERMINAL_CHAT_STATES.has(state)) {
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

    if (agentLevel === "none") {
      if (text.trim()) {
        this.appendPlainAssistantText(text);
      }

      if (TERMINAL_CHAT_STATES.has(state)) {
        this.finishResponse();
      }

      return;
    }

    const agentRun = this.ensureCurrentAgentRun(agentLevel, payload, data);
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
      this.completeAgentRun(agentLevel, payload, data);
      this.finishResponse();
      return;
    }

    this.publishMessages();
  }

  private handleSessionToolEvent(payload: GenericRecord) {
    const data = this.toRecord(payload.data) || payload;
    const phase = this.resolveString(data.phase || payload.phase).toLowerCase();
    const state = this.resolveString(payload.state || data.state).toLowerCase();
    const text = this.extractTextFromUnknown(
      data.text ??
        data.message ??
        data.content ??
        data.delta ??
        payload.delta ??
        payload.message ??
        payload.content ??
        payload.text,
    );
    const agentRun = this.ensureCurrentAgentRun("main", payload, data);
    if (!agentRun) {
      return;
    }

    agentRun.hasTool = true;
    this.appendToolSegment(agentRun, data, phase, text);

    if (TERMINAL_CHAT_STATES.has(state)) {
      this.completeAgentRun("main", payload, data);
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

  private resolveCreatedSessionKey(payload: GenericRecord | null | undefined) {
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

    const role = this.resolveString(record.role).toLowerCase();

    if (role === "user") {
      return this.buildHistoryMessage({
        role: "user",
        messageKind: "user",
        content: this.extractTextFromUnknown(
          record.content ?? record.message ?? record,
        ),
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
          tag: this.resolveToolCallTag(contentRecord),
          showToolIcon: true,
          collapsible: true,
          startsCollapsed: true,
        });

        return this.buildHistoryMessage({
          role: "assistant",
          messageKind: "assistant-tool-call",
          content: block.content,
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
          contentBlocks: [block],
        });
      }

      const fallbackBlock = this.buildContentBlock({
        kind: "text",
        content: this.extractAssistantTextForDisplay(
          record.content ?? record.message,
        ),
        title: "",
        subtitle: "",
        showToolIcon: false,
        collapsible: false,
        startsCollapsed: false,
      });

      if (!fallbackBlock.content) {
        return null;
      }

      return this.buildHistoryMessage({
        role: "assistant",
        messageKind: "assistant-text",
        content: fallbackBlock.content,
        contentBlocks: [fallbackBlock],
      });
    }

    return null;
  }

  private buildHistoryMessage(input: {
    role: ChatMessageView["role"];
    messageKind: ChatMessageView["messageKind"];
    content: string;
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
            tag: this.resolveToolCallTag(record),
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

        const fallbackContent = this.extractAssistantTextForDisplay(record);
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

  private extractAssistantTextForDisplay(value: unknown): string {
    if (typeof value === "string") {
      return value;
    }

    if (typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }

    if (Array.isArray(value)) {
      return value
        .map((item) => this.extractAssistantTextForDisplay(item))
        .filter(Boolean)
        .join("\n")
        .trim();
    }

    const record = this.toRecord(value);
    if (!record) {
      return "";
    }

    const candidates = [
      record.text,
      record.value,
      record.message,
      record.content,
    ];

    for (const candidate of candidates) {
      const resolvedText = this.extractAssistantTextForDisplay(candidate);
      if (resolvedText) {
        return resolvedText;
      }
    }

    return "";
  }

  private buildContentBlock(input: {
    kind: ChatMessageBlock["kind"];
    content: string;
    title: string;
    subtitle: string;
    tag?: string;
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
      tag: input.tag || "",
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
    this.activeAgentRunKeys.clear();
    this.currentToolSegmentIds.clear();
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

  private appendAssistantErrorBlock(text: string) {
    const trimmedText = text.trim();
    if (!trimmedText) {
      return;
    }

    const assistantMessage = this.ensureStreamingAssistantMessage();
    if (!assistantMessage) {
      return;
    }

    assistantMessage.contentBlocks = [
      {
        id: this.makeId(),
        kind: "error",
        content: trimmedText,
        title: "Error",
        subtitle: "",
        showToolIcon: false,
        collapsible: false,
        startsCollapsed: false,
      },
    ];
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

  private beginAgentRun(
    agentLevel: Exclude<AssistantAgentLevel, "none">,
    payload: GenericRecord,
    data: GenericRecord,
  ) {
    const assistantMessage = this.ensureStreamingAssistantMessage();
    if (!assistantMessage) {
      return null;
    }

    assistantMessage.messageKind = "assistant-agent-run";
    assistantMessage.contentBlocks = [];
    const runKey = this.getAgentRunKey(agentLevel, payload, data);
    const existingAgentRun = runKey
      ? this.findAgentRunByTrackedKey(assistantMessage, runKey)
      : null;
    if (existingAgentRun) {
      return existingAgentRun;
    }

    const agentRun: ChatAgentRun = {
      id: this.makeId(),
      agentLevel,
      title: this.resolveAgentRunTitle(agentLevel, payload, data),
      hasTool: false,
      isComplete: false,
      segments: [],
    };
    assistantMessage.agents.push(agentRun);

    if (runKey) {
      this.activeAgentRunKeys.set(runKey, agentRun.id);
    }

    this.currentToolSegmentIds.delete(agentRun.id);
    return agentRun;
  }

  private ensureCurrentAgentRun(
    agentLevel: Exclude<AssistantAgentLevel, "none">,
    payload: GenericRecord,
    data: GenericRecord,
  ) {
    const assistantMessage = this.ensureStreamingAssistantMessage();
    if (!assistantMessage) {
      return null;
    }

    assistantMessage.messageKind = "assistant-agent-run";
    const runKey = this.getAgentRunKey(agentLevel, payload, data);

    if (runKey) {
      const trackedAgentRun = this.findAgentRunByTrackedKey(
        assistantMessage,
        runKey,
      );
      if (trackedAgentRun) {
        trackedAgentRun.title =
          this.resolveAgentRunTitle(agentLevel, payload, data) ||
          trackedAgentRun.title;
        return trackedAgentRun;
      }
    }

    const lastRun = [...assistantMessage.agents]
      .reverse()
      .find((agent) => agent.agentLevel === agentLevel && !agent.isComplete);
    if (lastRun) {
      lastRun.title =
        this.resolveAgentRunTitle(agentLevel, payload, data) || lastRun.title;
      return lastRun;
    }

    return this.beginAgentRun(agentLevel, payload, data);
  }

  private completeAgentRun(
    agentLevel: Exclude<AssistantAgentLevel, "none">,
    payload: GenericRecord,
    data: GenericRecord,
  ) {
    if (!this.currentAssistantMessageId) {
      return;
    }

    const assistantMessage = this.messages.find(
      (message) => message.id === this.currentAssistantMessageId,
    );
    if (!assistantMessage) {
      return;
    }

    const runKey = this.getAgentRunKey(agentLevel, payload, data);
    const agentRun = runKey
      ? this.findAgentRunByTrackedKey(assistantMessage, runKey)
      : [...assistantMessage.agents]
          .reverse()
          .find(
            (agent) => agent.agentLevel === agentLevel && !agent.isComplete,
          );

    if (!agentRun) {
      if (runKey) {
        this.activeAgentRunKeys.delete(runKey);
      }
      return;
    }

    agentRun.isComplete = true;
    agentRun.segments.forEach((segment) => {
      segment.isComplete = true;
    });

    if (runKey) {
      this.activeAgentRunKeys.delete(runKey);
    }

    this.currentToolSegmentIds.delete(agentRun.id);
  }

  private handleAgentRunError(
    agentLevel: Exclude<AssistantAgentLevel, "none">,
    payload: GenericRecord,
    data: GenericRecord,
  ) {
    if (!this.currentAssistantMessageId) {
      return;
    }

    const assistantMessage = this.messages.find(
      (message) => message.id === this.currentAssistantMessageId,
    );
    if (!assistantMessage) {
      return;
    }

    const runKey = this.getAgentRunKey(agentLevel, payload, data);
    const agentRun = runKey
      ? this.findAgentRunByTrackedKey(assistantMessage, runKey)
      : [...assistantMessage.agents]
          .reverse()
          .find(
            (agent) => agent.agentLevel === agentLevel && !agent.isComplete,
          );

    if (!agentRun) {
      if (runKey) {
        this.activeAgentRunKeys.delete(runKey);
      }
      return;
    }

    agentRun.segments = agentRun.segments.filter(
      (segment) => !(segment.stream === "tool" && !segment.isComplete),
    );

    if (agentRun.segments.length === 0) {
      assistantMessage.agents = assistantMessage.agents.filter(
        (agent) => agent.id !== agentRun.id,
      );
    } else {
      agentRun.isComplete = true;
      agentRun.segments.forEach((segment) => {
        segment.isComplete = true;
      });
    }

    if (runKey) {
      this.activeAgentRunKeys.delete(runKey);
    }

    this.currentToolSegmentIds.delete(agentRun.id);
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

    assistantMessage.isCompleted = true;
    assistantMessage.agents.forEach((agent) => {
      agent.isComplete = true;
      agent.segments.forEach((segment) => {
        segment.isComplete = true;
      });
    });
    this.resetStreamingPointers();
  }

  private markHandshakeComplete() {
    if (this.isHandshakeComplete) {
      return;
    }

    this.isHandshakeComplete = true;
    this.setStatus("connected");
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

  private async refreshCatalogAndHistory() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }

    await this.loadCatalog();
    if (this.selectedSessionKey) {
      await this.loadHistory(this.selectedSessionKey);
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
    const segmentTitle = this.resolveToolSegmentTitle(phase);
    const segmentSubtitle = this.resolveToolSegmentSubtitle(
      data,
      agentRun.agentLevel,
    );
    const segmentContent = this.resolveToolSegmentContent(
      data,
      agentRun.agentLevel,
    );

    if (phase === "start") {
      const segment: ChatAgentSegment = {
        id: this.makeId(),
        stream: "tool",
        title: segmentTitle,
        subtitle: segmentSubtitle,
        content: segmentContent,
        isComplete: false,
      };
      agentRun.segments.push(segment);
      this.currentToolSegmentIds.set(agentRun.id, segment.id);
      return;
    }

    const segment = this.findCurrentToolSegment(agentRun);
    if (!segment) {
      const fallbackSegment: ChatAgentSegment = {
        id: this.makeId(),
        stream: "tool",
        title: segmentTitle,
        subtitle: segmentSubtitle,
        content: segmentContent,
        isComplete: false,
      };
      agentRun.segments.push(fallbackSegment);
      this.currentToolSegmentIds.set(agentRun.id, fallbackSegment.id);
    }

    const activeSegment = this.findCurrentToolSegment(agentRun);
    if (!activeSegment) {
      return;
    }

    activeSegment.title = segmentTitle || activeSegment.title;
    activeSegment.subtitle = segmentSubtitle || activeSegment.subtitle;

    if (!text.trim() && !activeSegment.content && segmentContent) {
      activeSegment.content = segmentContent;
    }

    if (phase === "result") {
      const resultRecord = this.toRecord(data.result);
      const resultContent = resultRecord
        ? this.resolveToolResultDisplayText(resultRecord)
        : "";
      activeSegment.content =
        resultContent ||
        this.formatToolSegmentMeta(data.meta ?? data.result ?? data);
      activeSegment.isComplete = true;
      this.currentToolSegmentIds.delete(agentRun.id);
      return;
    }

    if (text.trim()) {
      activeSegment.content = text;
    }

    if (phase === "end") {
      activeSegment.isComplete = true;
      this.currentToolSegmentIds.delete(agentRun.id);
    }
  }

  private findCurrentToolSegment(agentRun: ChatAgentRun) {
    const currentToolSegmentId = this.currentToolSegmentIds.get(agentRun.id);
    if (currentToolSegmentId) {
      const currentSegment = agentRun.segments.find(
        (segment) => segment.id === currentToolSegmentId,
      );
      if (currentSegment) {
        return currentSegment;
      }
    }

    return [...agentRun.segments]
      .reverse()
      .find((segment) => segment.stream === "tool" && !segment.isComplete);
  }

  private getAgentLevel(
    payload: GenericRecord,
    data: GenericRecord | null,
  ): AssistantAgentLevel {
    const sessionKey = this.getAgentSessionKey(payload, data);
    if (sessionKey === MAIN_AGENT_SESSION_KEY) {
      return "main";
    }

    if (sessionKey.indexOf(SUBAGENT_SESSION_KEY_PREFIX) !== -1) {
      return "sub";
    }

    return "none";
  }

  private getAgentSessionKey(
    payload: GenericRecord,
    data: GenericRecord | null,
  ) {
    const sessionKey = this.resolveString(
      payload.sessionKey || data?.sessionKey,
    );
    return sessionKey.trim();
  }

  private getAgentRunKey(
    agentLevel: Exclude<AssistantAgentLevel, "none">,
    payload: GenericRecord,
    data: GenericRecord | null,
  ) {
    const runId = this.resolveString(payload.runId || data?.runId).trim();
    if (runId) {
      return `${agentLevel}:run:${runId}`;
    }

    const sessionKey = this.getAgentSessionKey(payload, data);
    if (sessionKey) {
      return `${agentLevel}:session:${sessionKey}`;
    }

    return "";
  }

  private findAgentRunByTrackedKey(
    assistantMessage: ChatMessageView,
    runKey: string,
  ) {
    const agentRunId = this.activeAgentRunKeys.get(runKey);
    if (!agentRunId) {
      return null;
    }

    return (
      assistantMessage.agents.find((agent) => agent.id === agentRunId) || null
    );
  }

  private resolveAgentRunTitle(
    agentLevel: Exclude<AssistantAgentLevel, "none">,
    payload: GenericRecord,
    data: GenericRecord | null,
  ) {
    const titleCandidates = [
      data?.name,
      data?.displayName,
      data?.agentName,
      payload.name,
      payload.displayName,
      payload.agentName,
    ];

    for (const candidate of titleCandidates) {
      const normalized = this.resolveString(candidate).trim();
      if (normalized) {
        return normalized;
      }
    }

    return agentLevel === "sub" ? "Sub Agent" : "Main Agent";
  }

  private resolveToolSegmentTitle(phase: string) {
    if (phase === "result") {
      return "Tool output";
    }

    return "Tool";
  }

  private resolveToolSegmentSubtitle(
    data: GenericRecord,
    agentLevel?: Exclude<AssistantAgentLevel, "none">,
  ) {
    if (agentLevel === "sub") {
      return this.resolveString(data.name) || this.resolveString(data.toolName);
    }

    return this.resolveString(data.name) || this.resolveString(data.toolName);
  }

  private resolveToolSegmentContent(
    data: GenericRecord,
    agentLevel?: Exclude<AssistantAgentLevel, "none">,
  ) {
    const argsContent =
      data.args ?? data.arguments ?? data.params ?? data.input;
    if (argsContent !== undefined) {
      return this.formatToolPayloadAsJson(argsContent);
    }

    if (agentLevel === "sub") {
      return this.resolveString(data.title) || this.resolveString(data.meta);
    }

    return "";
  }

  private formatToolSegmentMeta(value: unknown) {
    return this.formatToolPayloadAsJson(value);
  }

  private isSubagentToolCall(record: GenericRecord | null | undefined) {
    return (
      this.resolveString(record?.arguments?.runtime).toLowerCase() ===
      "subagent"
    );
  }

  private resolveToolCallTag(record: GenericRecord | null | undefined) {
    return this.isSubagentToolCall(record) ? "SubAgent" : "";
  }

  private resolveToolCallSubtitle(record: GenericRecord | null | undefined) {
    if (!record) {
      return "";
    }

    return (
      this.resolveString(record.arguments?.query) ||
      this.resolveString(record.params?.query) ||
      this.resolveString(record.input?.query) ||
      this.resolveString(record.arguments?.prompt) ||
      this.resolveString(record.name)
    );
  }

  private resolveToolCallDisplayText(record: GenericRecord | null | undefined) {
    if (!record) {
      return "";
    }

    if (this.isSubagentToolCall(record)) {
      return this.resolveString(record.arguments?.task);
    }

    return (
      this.resolveString(record.arguments?.query) ||
      this.resolveString(record.params?.query) ||
      this.resolveString(record.input?.query) ||
      this.resolveString(record.arguments?.prompt) ||
      this.formatToolPayloadAsJson(
        record.arguments ?? record.params ?? record.input ?? record,
      )
    );
  }

  private resolveToolResultDisplayText(
    record: GenericRecord | null | undefined,
  ) {
    if (!record) {
      return "";
    }

    const preferredText = this.extractToolResultPreferredText(
      record.content ??
        record.result?.content ??
        record.result?.context ??
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
