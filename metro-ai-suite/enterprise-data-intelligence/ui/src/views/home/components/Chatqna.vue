<!--
  Copyright (C) 2026 Intel Corporation
  SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="chat-container">
    <div class="chat-header">
      <div class="header-left">
        <div class="knowledge-badge">
          <span class="badge-icon">
            <SvgIcon
              name="icon-chatbot1"
              :size="24"
              :style="{ color: 'var(--color-white)' }"
            />
          </span>
        </div>
        <div class="assistant-copy">
          <div class="assistant-title">{{ $t("chat.assistant") }}</div>
          <div class="assistant-subtitle">
            {{ $t("chat.housekeeperTagline") }}
          </div>
        </div>
      </div>
      <div class="header-right">
        <div v-if="selectedSessionLabel" class="selected-session-pill">
          {{ selectedSessionLabel }}
        </div>
        <a-popover
          placement="bottomRight"
          trigger="hover"
          overlay-class-name="session-history-popover"
        >
          <template #content>
            <div class="session-history-panel">
              <div class="session-history-title">
                {{ $t("chat.sessionPlaceholder") }}
              </div>
              <div
                v-if="isHistoryLoading && !displaySessionGroups.length"
                class="session-history-empty"
              >
                {{ $t("chat.loadingHistory") }}
              </div>
              <div
                v-for="group in displaySessionGroups"
                :key="group.agentId"
                class="session-agent-group"
              >
                <div class="session-agent-title">{{ group.displayName }}</div>
                <div v-if="group.description" class="session-agent-description">
                  {{ group.description }}
                </div>
                <button
                  v-for="session in group.sessions"
                  :key="session.key"
                  type="button"
                  class="session-history-item"
                  :class="{ active: session.key === selectedSessionKey }"
                  @click="handleSessionChange(session.key)"
                >
                  <span
                    v-if="session.key === selectedSessionKey"
                    class="session-history-check"
                  >
                    <SvgIcon
                      name="icon-copy-success"
                      :size="10"
                      :style="{ color: 'var(--color-white)' }"
                    />
                  </span>
                  <span class="session-history-name">
                    {{ buildSessionOptionLabel(session) }}
                  </span>
                </button>
              </div>
              <div
                v-if="!isHistoryLoading && !displaySessionGroups.length"
                class="session-history-empty"
              >
                {{ $t("chat.noSessions") }}
              </div>
            </div>
          </template>
          <button
            type="button"
            class="header-status session-history-trigger"
            :class="connectionStatus"
            :title="connectionStatusLabel"
            :disabled="!sessions.length && !isHistoryLoading"
          >
            <HistoryOutlined />
          </button>
        </a-popover>
      </div>
    </div>

    <div class="chatbot-wrap" :class="{ 'has-messages': hasMessages }">
      <div v-if="hasMessages" ref="scrollContainer" class="message-box">
        <div class="intel-markdown">
          <div ref="messageComponent">
            <div v-for="(msg, index) in messagesList" :key="msg.id">
              <MessageItem
                :message="msg"
                :message-index="index"
                :is-streaming="isStreaming"
                :last-query="isLastQuery(index)"
                :last-response="isLastResponse(index)"
                @preview="handleImagePreview"
                @send-question="handleSendFollowup"
              />
            </div>
          </div>
        </div>
      </div>

      <div class="chat-content" :class="{ 'full-height': !hasMessages }">
        <div v-if="!hasMessages" class="initial-input">
          <div class="welcome-card">
            <div class="welcome-eyebrow">{{ $t("chat.starterEyebrow") }}</div>
            <div class="welcome-title">{{ $t("chat.starterTitle") }}</div>
            <div class="welcome-description">
              {{ $t("chat.starterDescription") }}
            </div>
            <div v-if="isHistoryLoading" class="session-loading-tip">
              {{ $t("chat.loadingHistory") }}
            </div>
          </div>
        </div>

        <div
          ref="inputRef"
          class="input-wrap"
          :class="{ 'is-home': !hasMessages }"
        >
          <div v-if="!hasMessages" class="composer-copy">
            <div class="composer-title">{{ $t("chat.composerTitle") }}</div>
            <div class="composer-hint">
              {{
                selectedSessionKey
                  ? $t("chat.composerHint")
                  : $t("chat.noSessions")
              }}
            </div>
          </div>

          <div v-if="showScrollToBottomBtn && hasMessages" class="bottom-wrap">
            <div class="to-bottom" @click="scrollToBottom">
              <ArrowDownOutlined />
            </div>
          </div>

          <div class="composer-stack">
            <div v-if="showCommandPalette" class="command-palette">
              <div class="command-palette-header">
                <span class="command-palette-title">{{
                  $t("chat.commandPalette.title")
                }}</span>
                <span class="command-palette-tip">{{
                  $t("chat.commandPalette.tip")
                }}</span>
              </div>
              <div ref="commandPaletteScroll" class="command-palette-scroll">
                <div
                  v-for="group in filteredCommandGroups"
                  :key="group.category"
                  class="command-group"
                >
                  <div class="command-group-title">{{ group.label }}</div>
                  <button
                    v-for="option in group.commands"
                    :key="option.command"
                    type="button"
                    class="command-item"
                    :class="{
                      active: option.command === activeCommand?.command,
                    }"
                    :data-command-id="option.command"
                    @mousedown.prevent
                    @mouseenter="setActiveCommand(option.command)"
                    @click="handleCommandSelect(option)"
                  >
                    <span class="command-name">{{ option.command }}</span>
                    <a-tooltip placement="topLeft" :title="option.description">
                      <span class="command-description">{{
                        option.description
                      }}</span>
                    </a-tooltip>
                  </button>
                </div>
              </div>
              <div class="command-palette-shortcuts">
                <span class="command-shortcut-item">
                  <span class="command-shortcut-key">↑↓</span>
                  <span class="command-shortcut-label">{{
                    $t("chat.commandPalette.shortcuts.navigate")
                  }}</span>
                </span>
                <span class="command-shortcut-item">
                  <span class="command-shortcut-key">Tab</span>
                  <span class="command-shortcut-label">{{
                    $t("chat.commandPalette.shortcuts.fill")
                  }}</span>
                </span>
                <span class="command-shortcut-item">
                  <span class="command-shortcut-key">Enter</span>
                  <span class="command-shortcut-label">{{
                    $t("chat.commandPalette.shortcuts.send")
                  }}</span>
                </span>
                <span class="command-shortcut-item">
                  <span class="command-shortcut-key">Esc</span>
                  <span class="command-shortcut-label">{{
                    $t("chat.commandPalette.shortcuts.close")
                  }}</span>
                </span>
              </div>
            </div>

            <div class="input-container" :class="{ 'is-home': !hasMessages }">
              <a-textarea
                v-model:value.trim="inputKeywords"
                :placeholder="
                  selectedSessionKey ? $t('chat.tip4') : $t('chat.noSessions')
                "
                :auto-size="{ minRows: 1, maxRows: 4 }"
                :bordered="false"
                :disabled="!selectedSessionKey || isHistoryLoading"
                class="input-area"
                @input="handleInputChange"
                @keydown="handleComposerKeydown"
              />
              <div class="input-footer">
                <div class="footer-right">
                  <a-tooltip
                    placement="top"
                    :arrow="false"
                    :title="$t('chat.new')"
                  >
                    <span class="common-btn">
                      <SvgIcon
                        name="icon-newChat"
                        :style="{ color: 'var(--font-info-color)' }"
                        @click="handleCreateSession"
                      />
                    </span>
                  </a-tooltip>
                  <div class="divider"></div>
                  <a-button
                    type="primary"
                    class="action-btn"
                    shape="circle"
                    size="large"
                    :disabled="
                      (!isStreaming && !inputKeywords.trim()) ||
                      (!isStreaming &&
                        (!selectedSessionKey || isHistoryLoading))
                    "
                    @click="
                      isStreaming ? handleStopChat() : handleSendMessage()
                    "
                  >
                    <span v-if="!isStreaming" class="btn-icon">
                      <SvgIcon
                        name="icon-send2"
                        :size="18"
                        :style="{ color: 'var(--color-white)' }"
                      />
                    </span>
                    <span v-else class="btn-icon">
                      <SvgIcon
                        name="icon-chat-stop"
                        :size="18"
                        :style="{ color: 'var(--color-white)' }"
                      />
                    </span>
                  </a-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <a-image
    :style="{ display: 'none' }"
    :preview="{
      visible: imgVisible,
      onVisibleChange: handleImageVisible,
    }"
    :src="imageSrc"
  />
</template>

<script setup lang="ts">
import { ArrowDownOutlined, HistoryOutlined } from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import { throttle } from "lodash-es";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import {
  CHAT_COMMAND_DEFINITIONS,
  COMMAND_CATEGORY_ORDER,
  type ChatCommandDefinition,
} from "./chatCommandPalette.ts";
import { MessageItem } from "./index";
import {
  type ChatMessageView,
  type ChatSessionGroup,
  type ChatSessionSummary,
  type ConnectionStatus,
  WebSocketChatService,
} from "./WebSocketChatService";
import { sessionAppStore } from "@/store/session";

const sessionStore = sessionAppStore();
const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const messagesList = ref<ChatMessageView[]>([]);
const sessions = ref<ChatSessionSummary[]>([]);
const sessionGroups = ref<ChatSessionGroup[]>([]);
const selectedSessionKey = ref("");
const inputKeywords = ref("");
const scrollContainer = ref<HTMLElement | null>(null);
const messageComponent = ref<HTMLElement | null>(null);
const commandPaletteScroll = ref<HTMLElement | null>(null);
const showScrollToBottomBtn = ref(false);
const isStreaming = ref(false);
const isHistoryLoading = ref(false);
const isCreatingSession = ref(false);
const connectionStatus = ref<ConnectionStatus>("disconnected");
const activeCommandIndex = ref(0);
const isCommandPaletteDismissed = ref(false);

const imgVisible = ref(false);
const imageSrc = ref("");
const isUserScrolling = ref(false);
const resizeObserverRef = ref<ResizeObserver | null>(null);

const SCROLL_THRESHOLD = 80;
const DEFAULT_CHAT_WS_PORT =
  import.meta.env.VITE_CHATBOT_WS_PORT?.trim() || "18789";
const AUTH_TOKEN = import.meta.env.VITE_AUTH_TOKEN?.trim() || "";

const resolveSocketUrl = () => {
  const configuredUrl = import.meta.env.VITE_CHATBOT_URL?.trim();

  if (configuredUrl && configuredUrl !== "/") {
    if (configuredUrl.startsWith("/")) {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      return `${protocol}://${window.location.host}${configuredUrl}`;
    }

    return configuredUrl;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const hostname = window.location.hostname.includes(":")
    ? `[${window.location.hostname}]`
    : window.location.hostname;

  return `${protocol}://${hostname}:${DEFAULT_CHAT_WS_PORT}/`;
};

const WS_URL = resolveSocketUrl();

let throttledHandleScroll: ((event: Event) => void) | null = null;
let chatService: WebSocketChatService | null = null;

interface CommandOption extends ChatCommandDefinition {
  description: string;
  label: string;
}

const hasMessages = computed(() => messagesList.value.length > 0);
const routeSessionKey = computed(() => {
  const sessionKey = route.query.session;
  return typeof sessionKey === "string" ? sessionKey : "";
});
const lastQueryIndex = computed(() =>
  messagesList.value.map((messageItem) => messageItem.role).lastIndexOf("user"),
);
const lastResponseIndex = computed(() =>
  messagesList.value
    .map((messageItem) => messageItem.role)
    .lastIndexOf("assistant"),
);
const connectionStatusLabel = computed(() => {
  if (connectionStatus.value === "connected") {
    return t("chat.statusConnected");
  }

  if (connectionStatus.value === "connecting") {
    return t("chat.statusConnecting");
  }

  return t("chat.statusDisconnected");
});
const selectedSessionLabel = computed(() => {
  if (!selectedSessionKey.value) {
    return "";
  }

  const matchedSession = sessions.value.find(
    (session) => session.key === selectedSessionKey.value,
  );

  return matchedSession ? buildSessionOptionLabel(matchedSession) : "";
});
const displaySessionGroups = computed<ChatSessionGroup[]>(() => {
  if (sessionGroups.value.length) {
    return sessionGroups.value;
  }

  if (!sessions.value.length) {
    return [];
  }

  const groupedSessions = new Map<string, ChatSessionSummary[]>();
  sessions.value.forEach((session) => {
    const groupKey = session.agentId || "ungrouped";
    const nextSessions = groupedSessions.get(groupKey) || [];
    nextSessions.push(session);
    groupedSessions.set(groupKey, nextSessions);
  });

  return [...groupedSessions.entries()].map(([agentId, grouped]) => ({
    agentId,
    displayName: agentId === "ungrouped" ? "Unknown agent" : agentId,
    description: "",
    sessions: grouped,
  }));
});
const commandQuery = computed(() => {
  const normalizedValue = inputKeywords.value.trimStart();

  if (!normalizedValue.startsWith("/")) {
    return "";
  }

  return normalizedValue.slice(1).toLowerCase();
});
const commandOptions = computed<CommandOption[]>(() => {
  return CHAT_COMMAND_DEFINITIONS.map((option: ChatCommandDefinition) => ({
    ...option,
    label: t(`chat.commandCategories.${option.category.toLowerCase()}`),
    description: t(option.descriptionKey),
  }));
});
const filteredCommandOptions = computed<CommandOption[]>(() => {
  return filteredCommandGroups.value.flatMap((group) => group.commands);
});
const activeCommand = computed(() => {
  return filteredCommandOptions.value[activeCommandIndex.value] || null;
});
const filteredCommandGroups = computed(() => {
  const query = commandQuery.value;
  const matchedCommands = commandOptions.value.filter((option) => {
    if (!query) {
      return true;
    }

    const haystack = [option.command, option.description, ...option.keywords]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });

  return COMMAND_CATEGORY_ORDER.map((category) => ({
    category,
    label: t(`chat.commandCategories.${category.toLowerCase()}`),
    commands: matchedCommands.filter((option) => option.category === category),
  })).filter((group) => group.commands.length > 0);
});
const showCommandPalette = computed(() => {
  return (
    !isCommandPaletteDismissed.value &&
    inputKeywords.value.trimStart().startsWith("/") &&
    filteredCommandGroups.value.length > 0
  );
});

const isLastQuery = (index: number) => index === lastQueryIndex.value;
const isLastResponse = (index: number) => index === lastResponseIndex.value;

const getLastUserQuestion = () => {
  for (let index = messagesList.value.length - 1; index >= 0; index -= 1) {
    const messageItem = messagesList.value[index];
    if (messageItem?.role === "user" && messageItem.content) {
      return messageItem.content;
    }
  }

  return "";
};

const buildSessionOptionLabel = (session: ChatSessionSummary) => {
  return session.displayName || session.key;
};

const updateRouteSession = async (sessionKey: string) => {
  if (routeSessionKey.value === sessionKey) {
    return;
  }

  await router.replace({
    query: {
      ...route.query,
      session: sessionKey,
    },
  });
};

const applySessionSelection = async (sessionKey: string) => {
  if (!sessionKey) {
    return;
  }

  isUserScrolling.value = false;
  showScrollToBottomBtn.value = false;
  selectedSessionKey.value = sessionKey;
  sessionStore.setSessionId(sessionKey);
  chatService?.selectSession(sessionKey);
  await updateRouteSession(sessionKey);
  scrollToBottom();
};

const syncSessionFromRoute = async () => {
  if (!sessions.value.length) {
    selectedSessionKey.value = "";
    return;
  }

  const matchedSession = sessions.value.find(
    (session) => session.key === routeSessionKey.value,
  );
  const nextSessionKey = matchedSession?.key || sessions.value[0].key;

  if (!nextSessionKey) {
    return;
  }

  if (
    selectedSessionKey.value === nextSessionKey &&
    routeSessionKey.value === nextSessionKey
  ) {
    return;
  }

  await applySessionSelection(nextSessionKey);
};

const scrollToBottom = () => {
  nextTick(() => {
    const element = scrollContainer.value;
    if (!element) {
      return;
    }

    element.scrollTop = element.scrollHeight;
    isUserScrolling.value = false;
    showScrollToBottomBtn.value = false;
  });
};

const handleResize = () => {
  nextTick(() => {
    const element = scrollContainer.value;
    if (!isUserScrolling.value && element) {
      element.scrollTop = element.scrollHeight;
    }
  });
};

const initResizeObserver = () => {
  if (!messageComponent.value) {
    return;
  }

  resizeObserverRef.value?.disconnect();
  resizeObserverRef.value = new ResizeObserver(handleResize);
  resizeObserverRef.value.observe(messageComponent.value);
};

const handleScroll = () => {
  const element = scrollContainer.value;
  if (!element) {
    return;
  }

  const distanceToBottom =
    element.scrollHeight - element.scrollTop - element.clientHeight;
  if (distanceToBottom > SCROLL_THRESHOLD) {
    isUserScrolling.value = true;
    showScrollToBottomBtn.value = true;
  } else {
    isUserScrolling.value = false;
    showScrollToBottomBtn.value = false;
  }
};

const bindScrollListener = () => {
  if (!scrollContainer.value) {
    return;
  }

  if (throttledHandleScroll) {
    scrollContainer.value.removeEventListener("scroll", throttledHandleScroll);
  }

  const scrollListener = throttle(handleScroll, 100);
  throttledHandleScroll = scrollListener;
  scrollContainer.value.addEventListener("scroll", scrollListener);
};

const setActiveCommand = (command: string) => {
  const commandIndex = filteredCommandOptions.value.findIndex(
    (option) => option.command === command,
  );
  if (commandIndex >= 0) {
    activeCommandIndex.value = commandIndex;
  }
};

const syncActiveCommandIntoView = () => {
  nextTick(() => {
    const activeOption = activeCommand.value;
    const paletteElement = commandPaletteScroll.value;
    if (!activeOption || !paletteElement) {
      return;
    }

    const activeElement = paletteElement.querySelector<HTMLElement>(
      `[data-command-id="${activeOption.command}"]`,
    );
    activeElement?.scrollIntoView({ block: "nearest" });
  });
};

const handleCommandArrow = (direction: "up" | "down", event: KeyboardEvent) => {
  if (!showCommandPalette.value || filteredCommandOptions.value.length === 0) {
    return;
  }

  event.preventDefault();

  const lastIndex = filteredCommandOptions.value.length - 1;
  if (direction === "down") {
    activeCommandIndex.value =
      activeCommandIndex.value >= lastIndex ? 0 : activeCommandIndex.value + 1;
  } else {
    activeCommandIndex.value =
      activeCommandIndex.value <= 0 ? lastIndex : activeCommandIndex.value - 1;
  }

  syncActiveCommandIntoView();
};

const handleCommandTab = (event: KeyboardEvent) => {
  if (!showCommandPalette.value || !activeCommand.value) {
    return;
  }

  event.preventDefault();
  isCommandPaletteDismissed.value = true;
  inputKeywords.value = activeCommand.value.command;
};

const handleCommandEscape = (event: KeyboardEvent) => {
  if (!showCommandPalette.value) {
    return;
  }

  event.preventDefault();
  isCommandPaletteDismissed.value = true;
};

const handleEnterPress = (event: KeyboardEvent) => {
  if (showCommandPalette.value && activeCommand.value) {
    event.preventDefault();
    isCommandPaletteDismissed.value = true;
    void handleCommandSelect(activeCommand.value);
    return;
  }

  event.preventDefault();
  void handleSendMessage();
};

const handleComposerKeydown = (event: KeyboardEvent) => {
  switch (event.key) {
    case "Enter":
      handleEnterPress(event);
      return;
    case "ArrowUp":
      handleCommandArrow("up", event);
      return;
    case "ArrowDown":
      handleCommandArrow("down", event);
      return;
    case "Tab":
      handleCommandTab(event);
      return;
    case "Escape":
      handleCommandEscape(event);
      return;
    default:
      return;
  }
};

const handleSendFollowup = (question?: string) => {
  if (isStreaming.value) {
    message.warning(t("chat.followupWait"));
    return;
  }

  const nextQuestion = question || getLastUserQuestion();
  if (!nextQuestion) {
    return;
  }

  inputKeywords.value = nextQuestion;
  void handleSendMessage();
};

const handleInputChange = () => {
  if (inputKeywords.value.trimStart().startsWith("/")) {
    isCommandPaletteDismissed.value = false;
  }
};

const handleCommandSelect = async (option: CommandOption) => {
  if (option.command === "/stop" && isStreaming.value) {
    inputKeywords.value = "";
    handleStopChat();
    return;
  }

  inputKeywords.value = "";
  await submitQuestion(option.command);
};

const submitQuestion = async (question: string) => {
  const normalizedQuestion = question.trim();
  if (!normalizedQuestion || !chatService || !selectedSessionKey.value) {
    return;
  }

  const isNewSessionCommand = normalizedQuestion === "/new";
  if (isNewSessionCommand) {
    if (
      isHistoryLoading.value ||
      isStreaming.value ||
      isCreatingSession.value
    ) {
      return;
    }

    isCreatingSession.value = true;
  } else if (isStreaming.value) {
    return;
  }

  try {
    isUserScrolling.value = false;
    const nextSessionKey = await chatService.sendChat(normalizedQuestion);

    if (!isNewSessionCommand) {
      scrollToBottom();
      return;
    }

    if (!nextSessionKey) {
      scrollToBottom();
      return;
    }

    await applySessionSelection(nextSessionKey);
  } finally {
    if (isNewSessionCommand) {
      isCreatingSession.value = false;
    }
  }
};

const handleCreateSession = async () => {
  await submitQuestion("/new");
};

const handleSendMessage = async () => {
  if (
    !inputKeywords.value.trim() ||
    isStreaming.value ||
    !selectedSessionKey.value
  ) {
    return;
  }

  const question = inputKeywords.value.trim();
  inputKeywords.value = "";
  await submitQuestion(question);
};

const handleStopChat = () => {
  if (!chatService) {
    return;
  }

  isStreaming.value = false;
  chatService.cancel();
};

const handleSessionChange = (sessionKey: string) => {
  if (!sessionKey || sessionKey === selectedSessionKey.value) {
    return;
  }

  if (isStreaming.value) {
    handleStopChat();
  }

  void updateRouteSession(sessionKey);
};

const handleImagePreview = (url: string) => {
  imageSrc.value = url;
  handleImageVisible(true);
};

const handleImageVisible = (value = false) => {
  imgVisible.value = value;
};

watch(hasMessages, (hasAnyMessages) => {
  if (!hasAnyMessages) {
    return;
  }

  nextTick(() => {
    bindScrollListener();
    initResizeObserver();
  });
});

watch(
  () => messageComponent.value,
  (messageElement) => {
    if (!messageElement) {
      return;
    }

    nextTick(() => initResizeObserver());
  },
  { immediate: true },
);

watch(
  [sessions, routeSessionKey],
  () => {
    void syncSessionFromRoute();
  },
  { immediate: true },
);

watch(
  messagesList,
  () => {
    if (!isUserScrolling.value) {
      scrollToBottom();
    }
  },
  { deep: true },
);

watch(showCommandPalette, (visible) => {
  if (!visible) {
    activeCommandIndex.value = 0;
    return;
  }

  activeCommandIndex.value = 0;
  syncActiveCommandIntoView();
});

watch(commandQuery, () => {
  activeCommandIndex.value = 0;
  if (showCommandPalette.value) {
    syncActiveCommandIntoView();
  }
});

onUnmounted(() => {
  chatService?.disconnect();

  if (scrollContainer.value && throttledHandleScroll) {
    scrollContainer.value.removeEventListener("scroll", throttledHandleScroll);
  }

  resizeObserverRef.value?.disconnect();
});

onMounted(() => {
  chatService = new WebSocketChatService({
    url: WS_URL,
    authToken: AUTH_TOKEN,
    onMessagesChange: (messages: ChatMessageView[]) => {
      messagesList.value = messages;
    },
    onSessionsChange: (
      nextSessions: ChatSessionSummary[],
      nextSessionGroups: ChatSessionGroup[],
    ) => {
      sessions.value = nextSessions;
      sessionGroups.value = nextSessionGroups;
    },
    onHistoryLoadingChange: (loading: boolean) => {
      isHistoryLoading.value = loading;
    },
    onStreamingChange: (streaming: boolean) => {
      isStreaming.value = streaming;
    },
    onStatusChange: (status: ConnectionStatus) => {
      connectionStatus.value = status;
    },
    onError: (errorMessage: string) => {
      message.error(errorMessage);
    },
  });

  chatService.connect();
});
</script>

<style scoped lang="less">
.chat-container {
  height: 100%;
  .flex-column;
  background: var(--surface-panel-bg);
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 20px 16px;
  border-bottom: 1px solid var(--border-primary);
  background: var(--surface-glass-bg);
  backdrop-filter: blur(12px);

  .header-left {
    .flex-left;
    gap: 14px;
  }

  .assistant-copy {
    .flex-column;
    gap: 4px;
  }

  .assistant-title {
    font-size: var(--font-size-16);
    font-weight: 700;
    color: var(--font-main-color);
  }

  .assistant-subtitle {
    font-size: var(--font-size-11);
    color: var(--font-tip-color);
  }

  .knowledge-badge {
    .flex-left;

    .badge-icon {
      height: 38px;
      width: 38px;
      background: var(--color-primary-second);
      border-radius: 12px;
      box-shadow: 0 8px 16px var(--bg-box-shadow);
      .vertical-center;
    }
  }

  .header-right {
    .flex-left;
    gap: 10px;
    min-width: 0;
  }

  .selected-session-pill {
    max-width: 240px;
    min-width: 0;
    padding: 7px 12px;
    border-radius: 999px;
    border: 1px solid var(--border-primary);
    background: color-mix(in srgb, var(--surface-card-bg) 88%, transparent);
    color: var(--font-main-color);
    font-size: var(--font-size-12);
    font-weight: 600;
    line-height: 1.2;
    .single-ellipsis;
  }

  .header-status {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 999px;
    border: 1px solid var(--border-primary);
    font-size: var(--font-size-14);
    cursor: pointer;
    transition: all 0.2s ease;

    &.connected {
      background: var(--color-successBg);
      color: var(--color-success);
      border-color: var(--border-success);
    }

    &.connecting {
      background: var(--color-warningBg);
      color: var(--color-warning-strong);
      border-color: var(--border-warning);
    }

    &.disconnected {
      background: var(--surface-card-bg-hover);
      color: var(--font-tip-color);
    }

    &:disabled {
      cursor: default;
      opacity: 0.6;
    }
  }

  .session-history-trigger:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 16px var(--bg-box-shadow);
  }
}

.session-history-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 220px;
  max-width: 280px;
  max-height: min(60vh, 520px);
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}

.session-history-title {
  font-size: var(--font-size-12);
  font-weight: 700;
  color: var(--font-main-color);
}

.session-agent-group {
  .flex-column;
  gap: 4px;
  padding-left: 8px;
  border-left: 1px solid
    color-mix(in srgb, var(--border-primary) 65%, transparent);
}

.session-agent-title {
  font-size: var(--font-size-12);
  font-weight: 700;
  color: var(--font-main-color);
  padding-left: 2px;
}

.session-agent-description {
  font-size: var(--font-size-11);
  line-height: 1.5;
  color: var(--font-tip-color);
  display: none;
}

.session-history-item {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  color: var(--font-text-color);
  padding: 8px 28px 8px 10px;
  border: 1px solid var(--border-primary);
  border-radius: 10px;
  background: color-mix(in srgb, var(--surface-card-bg) 82%, transparent);
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover,
  &.active {
    border-color: var(--color-primary-second);
    background: color-mix(
      in srgb,
      var(--surface-card-bg-hover) 85%,
      transparent
    );
    box-shadow: 0 6px 14px
      color-mix(in srgb, var(--bg-box-shadow) 55%, transparent);
  }
}

.session-history-name {
  width: 100%;
  font-size: var(--font-size-12);
  .single-ellipsis;
}

.session-history-check {
  position: absolute;
  top: 6px;
  right: 8px;
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--color-primary-second);
  color: var(--color-white);
  font-size: var(--font-size-11);
  font-weight: 700;
  box-shadow: 0 4px 10px
    color-mix(in srgb, var(--bg-box-shadow) 55%, transparent);
}

.session-history-empty {
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--surface-card-bg);
  color: var(--font-tip-color);
  font-size: var(--font-size-12);
}

.chatbot-wrap {
  .vertical-between;
  width: 100%;
  flex: 1;
  min-height: 0;

  &.has-messages {
    justify-content: flex-start;

    .chat-content {
      flex-shrink: 0;
      padding: 10px 0 20px 0;
    }
  }
}

.chat-content {
  width: 100%;
  .flex-column;
  align-items: center;
  gap: 32px;
  flex-shrink: 0;
  max-width: 100%;
  overflow: visible;

  &.full-height {
    flex: 1;
    height: 100%;
    justify-content: center;
  }
}

.message-box {
  flex: 1;
  width: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  justify-content: center;
  padding: 20px 0 10px;
  max-height: calc(100vh - 300px);

  .intel-markdown {
    width: 85%;
    max-width: 1000px;
    padding: 0 20px;
  }
}

.initial-input {
  width: 85%;
  max-width: 960px;
  flex-shrink: 0;
  padding: 0 20px;

  .welcome-card {
    text-align: left;
    padding: 28px;
    border: 1px solid color-mix(in srgb, var(--border-primary) 72%, white);
    border-radius: 28px;
    background:
      radial-gradient(
        circle at top right,
        color-mix(in srgb, var(--color-primaryBg) 92%, white) 0%,
        transparent 34%
      ),
      linear-gradient(
        135deg,
        color-mix(in srgb, var(--surface-card-bg) 95%, white) 0%,
        color-mix(in srgb, var(--surface-card-bg-hover) 88%, white) 100%
      );
    box-shadow: 0 22px 46px
      color-mix(in srgb, var(--bg-box-shadow) 85%, transparent);
  }

  .welcome-eyebrow {
    font-size: var(--font-size-12);
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--color-primary-second);
  }

  .welcome-title {
    margin-top: 14px;
    font-size: 34px;
    line-height: 1.08;
    font-weight: 700;
    color: var(--font-main-color);
    letter-spacing: -0.03em;
  }

  .welcome-description {
    margin-top: 12px;
    font-size: var(--font-size-15);
    line-height: 1.7;
    color: var(--font-text-color);
  }

  .tip-wrap {
    margin-top: 18px;
    max-width: 680px;
    font-size: var(--font-size-14);
    line-height: 1.6;
    color: var(--font-text-color);
    display: flex;
    align-items: center;
    gap: 6px;

    .bulb-icon {
      font-size: var(--font-size-14);
      color: var(--color-primary-second);
    }
  }

  .session-loading-tip {
    margin-top: 12px;
    font-size: var(--font-size-12);
    color: var(--font-tip-color);
  }
}

.input-wrap {
  width: 85%;
  max-width: 960px;
  position: relative;
  box-sizing: border-box;
  padding: 0 20px 12px;
  flex-shrink: 0;

  .composer-copy {
    margin-bottom: 14px;
    padding: 0 4px;
  }

  .composer-hint {
    margin-top: 6px;
    font-size: var(--font-size-13);
    line-height: 1.6;
    color: var(--font-tip-color);
  }

  .bottom-wrap {
    position: absolute;
    top: -40px;
    width: 100%;
    height: 32px;
    .vertical-center;

    .to-bottom {
      position: fixed;
      .vertical-center;
      width: 32px;
      height: 32px;
      cursor: pointer;
      z-index: 20;
      border-radius: 50%;
      background-color: var(--bg-card-color);
      border: 1px solid var(--border-main-color);
      box-shadow: 0px 2px 4px 0px var(--bg-box-shadow);

      &:hover {
        background-color: var(--color-primarySoft);
        border: 1px solid var(--color-primary-second);

        .anticon-arrow-down {
          color: var(--color-primary-second);
        }
      }
    }
  }
}

.composer-stack {
  position: relative;
}

.command-palette {
  position: absolute;
  right: 0;
  bottom: calc(100% + 10px);
  left: 0;
  z-index: 25;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--border-primary) 76%, white);
  border-radius: 18px;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--surface-panel-bg) 98%, white) 0%,
    color-mix(in srgb, var(--surface-card-bg) 94%, white) 100%
  );
  box-shadow:
    0 16px 32px color-mix(in srgb, var(--bg-box-shadow) 82%, transparent),
    inset 0 1px 0 color-mix(in srgb, white 78%, transparent);
  backdrop-filter: blur(12px);
}

.command-palette-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.command-palette-title {
  font-size: var(--font-size-13);
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--font-main-color);
}

.command-palette-tip {
  font-size: var(--font-size-11);
  color: var(--font-tip-color);
}

.command-palette-scroll {
  max-height: 320px;
  overflow-y: auto;
  overflow-x: hidden;
}

.command-palette-shortcuts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  padding-top: 10px;
  margin-top: 10px;
  border-top: 1px solid
    color-mix(in srgb, var(--border-primary) 70%, transparent);
}

.command-shortcut-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.command-shortcut-key {
  padding: 2px 6px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--surface-card-bg-hover) 88%, white);
  color: var(--font-main-color);
  font-size: var(--font-size-11);
  font-weight: 700;
  line-height: 1.2;
}

.command-shortcut-label {
  color: var(--font-tip-color);
  font-size: var(--font-size-11);
  line-height: 1.4;
}

.command-group + .command-group {
  margin-top: 12px;
}

.command-group-title {
  margin-bottom: 4px;
  font-size: var(--font-size-11);
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-primary-second);
}

.command-item {
  width: 100%;
  min-height: 32px;
  padding: 0 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  display: grid;
  grid-template-columns: 92px minmax(0, 1fr);
  align-items: center;
  column-gap: 10px;
  text-align: left;
  cursor: pointer;
  transition: all 0.18s ease;

  &:hover,
  &.active {
    background: var(--surface-card-bg-hover);
  }
}

.command-item + .command-item {
  margin-top: 2px;
}

.command-name {
  font-size: var(--font-size-13);
  font-weight: 600;
  color: var(--font-main-color);
}

.command-description {
  font-size: var(--font-size-12);
  line-height: 1.4;
  color: var(--font-tip-color);
  text-align: right;
  .single-ellipsis;
}

.input-container {
  width: 100%;
  border: 1px solid var(--border-primary);
  border-radius: 22px;
  background: var(--surface-card-bg);
  padding: 12px 14px 8px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.2s;
  box-shadow: 0 10px 22px var(--bg-box-shadow);

  &:focus-within {
    border-color: var(--color-primary-second);
    box-shadow: 0 12px 26px var(--bg-box-shadow);
  }
}

.input-wrap.is-home {
  .composer-copy {
    margin-bottom: 14px;
    padding: 0 4px;
  }

  .composer-title {
    font-size: 20px;
    line-height: 1.2;
    font-weight: 700;
    color: var(--font-main-color);
    letter-spacing: -0.02em;
  }

  .composer-hint {
    margin-top: 6px;
    font-size: var(--font-size-13);
    line-height: 1.6;
    color: var(--font-tip-color);
  }
}

.input-container.is-home {
  border: 1px solid color-mix(in srgb, var(--border-primary) 78%, white);
  border-radius: 28px;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--surface-panel-bg) 96%, white) 0%,
    color-mix(in srgb, var(--surface-card-bg) 90%, white) 100%
  );
  padding: 18px 18px 12px;
  gap: 12px;
  box-shadow:
    0 20px 44px color-mix(in srgb, var(--bg-box-shadow) 92%, transparent),
    inset 0 1px 0 color-mix(in srgb, white 78%, transparent);

  &:focus-within {
    border-color: var(--color-primary-second);
    transform: translateY(-1px);
    box-shadow:
      0 24px 52px color-mix(in srgb, var(--bg-box-shadow) 96%, transparent),
      0 0 0 4px color-mix(in srgb, var(--color-primaryBg) 68%, transparent);
  }
}

.input-area {
  width: 100%;
  padding: 0;
  font-size: var(--font-size-14);
  line-height: 1.6;
  color: var(--font-main-color);
  resize: none;
  box-sizing: border-box;
  transition: opacity 0.2s;

  &:focus {
    outline: none;
    box-shadow: none;
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }
}

.input-container.is-home .input-area {
  font-size: var(--font-size-15);
  line-height: 1.75;
}

.input-footer {
  width: 100%;
  .flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.footer-right {
  .flex-left;
  gap: 12px;
  flex-shrink: 0;
}
.common-btn {
  width: 36px;
  height: 36px;
  .vertical-center;
  border-radius: 10px;
  cursor: pointer;
  font-size: var(--font-size-14);
  transition: all 0.2s;
  background: var(--color-primaryBg);
  border: 1px solid var(--border-primary);

  &:hover {
    background: var(--surface-card-bg-hover);
    border-color: var(--color-primary-second);
  }
}

.divider {
  width: 1px;
  height: 18px;
  background: var(--border-primary);
}
.action-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: var(--color-primary-second);
  box-shadow: 0 8px 18px var(--bg-box-shadow);

  &:hover,
  &:focus {
    background: var(--color-primary-hover);
  }
}

@media (max-width: 768px) {
  .chat-header {
    align-items: flex-start;
    gap: 12px;
    flex-direction: column;

    .header-right {
      width: 100%;
      justify-content: flex-end;
    }
  }

  .message-box .intel-markdown {
    width: 100%;
    padding: 0 12px;
  }

  .initial-input .welcome-card {
    padding: 18px 16px;
  }

  .initial-input .welcome-title {
    font-size: 26px;
  }

  .input-wrap {
    padding: 0 12px;
  }

  .command-palette {
    padding: 12px;
  }

  .command-palette-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .command-item {
    grid-template-columns: 82px minmax(0, 1fr);
  }

  .command-palette-shortcuts {
    gap: 8px 10px;
  }

  .input-wrap.is-home .composer-title {
    font-size: 18px;
  }
}
</style>
