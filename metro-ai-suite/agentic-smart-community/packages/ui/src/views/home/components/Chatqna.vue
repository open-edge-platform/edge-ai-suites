<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="chat-container flex-column">
    <div class="chat-header">
      <div class="header-left flex-left">
        <div class="knowledge-badge">
          <span class="badge-icon">
            <SvgIcon name="icon-chatbot1" inherit :size="22" />
          </span>
        </div>
        <div class="assistant-copy flex-column">
          <div class="assistant-title">{{ $t("chat.assistant") }}</div>
          <div class="assistant-subtitle">
            {{ $t("chat.housekeeperTagline") }}
          </div>
        </div>
      </div>
      <div class="header-right flex-left">
        <div
          v-if="selectedSessionLabel"
          class="selected-session-pill"
          :title="selectedSessionLabel"
        >
          {{ selectedSessionLabel }}
        </div>
        <a-tooltip :title="$t('chat.frameworkSettings')">
          <button
            type="button"
            class="header-status"
            :title="$t('chat.frameworkSettings')"
            @click="frameworkSettingsOpen = !frameworkSettingsOpen"
          >
            <SettingOutlined />
          </button>
        </a-tooltip>
        <a-popover
          placement="bottomRight"
          trigger="hover"
          overlay-class-name="session-history-popover"
        >
          <template #content>
            <div class="session-history-panel flex-column">
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
                class="session-agent-group flex-column"
              >
                <div class="session-agent-title">
                  {{ buildAgentGroupLabel(group) }}
                </div>
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
                  <span
                    class="session-history-name single-ellipsis"
                    :title="buildSessionDropdownLabel(session)"
                  >
                    {{ buildSessionDropdownLabel(session) }}
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

    <div
      class="chatbot-wrap"
      :class="{
        'has-messages': hasMessages,
        'has-framework-card': showFrameworkCard,
      }"
    >
      <div v-if="showFrameworkCard" class="framework-card flex-column">
        <div class="framework-card-head flex-between">
          <div class="framework-card-copy flex-column">
            <div class="framework-card-title">
              {{
                frameworkConfigured
                  ? $t("chat.frameworkTitle")
                  : $t("chat.frameworkUnconfiguredTitle")
              }}
            </div>
            <div class="framework-card-description">
              {{
                frameworkConfigured
                  ? $t("chat.frameworkConfiguredDescription")
                  : $t("chat.frameworkUnconfiguredDescription")
              }}
            </div>
          </div>
          <button
            v-if="frameworkConfigured"
            type="button"
            class="framework-card-close"
            :title="$t('common.cancel')"
            @click="closeFrameworkSettings"
          >
            ×
          </button>
        </div>

        <div class="framework-supported-label">
          {{ $t("chat.frameworkSupported") }}
        </div>
        <div class="framework-options flex-left">
          <button
            v-for="framework in agentFrameworks"
            :key="framework.id"
            type="button"
            class="framework-option"
            :class="{ active: framework.id === selectedFrameworkId && frameworkFormOpen }"
            @click="selectFramework(framework)"
          >
            {{ framework.label }}
          </button>
        </div>

        <div v-if="frameworkFormOpen" class="framework-form flex-column">
          <div class="framework-field flex-column">
            <label for="agent-framework-url">{{ $t("chat.frameworkUrl") }}</label>
            <a-input
              id="agent-framework-url"
              v-model:value.trim="frameworkUrl"
              placeholder="http://127.0.0.1:18789/"
            />
          </div>
          <div class="framework-field flex-column">
            <label for="agent-framework-token">{{ $t("chat.frameworkToken") }}</label>
            <a-input-password
              id="agent-framework-token"
              v-model:value="frameworkToken"
              :placeholder="$t('chat.frameworkTokenPlaceholder')"
              autocomplete="off"
            />
          </div>
          <div class="framework-cache-note">{{ $t("chat.frameworkCacheNote") }}</div>
          <div class="framework-actions flex-end">
            <a-button @click="frameworkFormOpen = false">
              {{ $t("common.cancel") }}
            </a-button>
            <a-button
              type="primary"
              :loading="frameworkSaving"
              @click="handleFrameworkConfigure"
            >
              {{ $t("chat.frameworkConnect") }}
            </a-button>
          </div>
        </div>
      </div>

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

      <div
        class="chat-content flex-column"
        :class="{ 'full-height': !hasMessages }"
      >
        <div v-if="!hasMessages" class="initial-input">
          <div class="welcome-card">
            <div class="welcome-eyebrow">{{ $t("chat.housekeeperLabel") }}</div>
            <div class="tip-wrap flex-left">
              <span class="bulb-icon">✦</span>
              {{ $t("chat.tip3") }}
            </div>
            <div v-if="isHistoryLoading" class="session-loading-tip">
              {{ $t("chat.loadingHistory") }}
            </div>
            <div class="capability-list">
              <button
                v-for="item in quickActions"
                :key="item"
                type="button"
                class="capability-chip"
                @click="handleQuickAction(item)"
              >
                {{ item }}
              </button>
            </div>
          </div>
        </div>

        <div ref="inputRef" class="input-wrap">
          <div
            v-if="showScrollToBottomBtn && hasMessages"
            class="bottom-wrap vertical-center"
          >
            <div class="to-bottom vertical-center" @click="scrollToBottom">
              <ArrowDownOutlined />
            </div>
          </div>

          <div class="input-container flex-column">
            <a-textarea
              v-model:value.trim="inputKeywords"
              :placeholder="
                selectedSessionKey ? $t('chat.tip4') : $t('chat.noSessions')
              "
              :auto-size="{ minRows: 1, maxRows: 4 }"
              :bordered="false"
              :disabled="!selectedSessionKey || isHistoryLoading"
              class="input-area"
              @keydown.enter.prevent="handleEnterPress"
            />
            <div class="input-footer flex-end">
              <div class="footer-right flex-left">
                <a-tooltip
                  placement="top"
                  :arrow="false"
                  :title="$t('chat.refresh')"
                >
                  <button
                    type="button"
                    class="common-btn toolbar-icon-btn"
                    :class="{
                      spinning:
                        isHistoryLoading || connectionStatus === 'connecting',
                    }"
                    :title="$t('chat.refresh')"
                    :disabled="isHistoryLoading || isStreaming"
                    @click="handleRefreshHistory"
                  >
                    <ReloadOutlined />
                  </button>
                </a-tooltip>
                <a-tooltip
                  placement="top"
                  :arrow="false"
                  :title="$t('chat.new')"
                >
                  <span class="common-btn">
                    <SvgIcon
                      name="icon-newChat"
                      :size="18"
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
                    (!isStreaming && (!selectedSessionKey || isHistoryLoading))
                  "
                  @click="isStreaming ? handleStopChat() : handleSendMessage()"
                >
                  <span v-if="!isStreaming" class="btn-icon">
                    <SvgIcon
                      name="icon-send2"
                      :size="16"
                      :style="{ color: 'var(--color-white)' }"
                    />
                  </span>
                  <span v-else class="btn-icon">
                    <SvgIcon
                      name="icon-chat-stop"
                      :size="16"
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
import {
  ArrowDownOutlined,
  HistoryOutlined,
  ReloadOutlined,
  SettingOutlined,
} from "@ant-design/icons-vue";
import { message } from "ant-design-vue";
import { throttle } from "lodash-es";
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { MessageItem } from "./index";
import {
  type ChatMessageView,
  type ChatSessionGroup,
  type ChatSessionSummary,
  type ConnectionStatus,
  WebSocketChatService,
} from "./WebSocketChatService";
import { sessionAppStore } from "@/store/session";
import {
  configureAgentFramework,
  getDashboardConfig,
  type AgentFrameworkOption,
} from "@/api/smartHome";

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
const showScrollToBottomBtn = ref(false);
const isStreaming = ref(false);
const isHistoryLoading = ref(false);
const isCreatingSession = ref(false);
const connectionStatus = ref<ConnectionStatus>("disconnected");
const frameworkConfigured = ref(false);
const frameworkSettingsOpen = ref(false);
const frameworkFormOpen = ref(false);
const frameworkSaving = ref(false);
const agentFrameworks = ref<AgentFrameworkOption[]>([]);
const selectedFrameworkId = ref<AgentFrameworkOption["id"]>("openclaw");
const frameworkUrl = ref("http://127.0.0.1:18789/");
const frameworkToken = ref("");

const imgVisible = ref(false);
const imageSrc = ref("");
const isUserScrolling = ref(false);
const resizeObserverRef = ref<ResizeObserver | null>(null);

const SCROLL_THRESHOLD = 80;
const SOURCE_AGENT_NAME_MAP: Record<string, string> = {
  cam_fridge: "fridge-agent-en",
  cam_child: "child-safety-agent",
  cam_elder_bedroom: "elder-wakeup-agent",
  cam_elder_bedroom_2: "elder-wakeup-agent",
};
const AUTH_TOKEN = "";

const resolveSocketUrl = () => {
  const configuredUrl = import.meta.env.VITE_CHATBOT_URL?.trim();

  if (configuredUrl && configuredUrl !== "/") {
    return configuredUrl;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/chat`;
};

const WS_URL = resolveSocketUrl();
let throttledHandleScroll: ((event: Event) => void) | null = null;
let chatService: WebSocketChatService | null = null;
let lastAutoSelectedSourceId = "";

const selectFramework = (framework: AgentFrameworkOption) => {
  selectedFrameworkId.value = framework.id;
  frameworkUrl.value = frameworkUrl.value || framework.defaultUrl;
  frameworkFormOpen.value = true;
};

const showFrameworkCard = computed(
  () => !frameworkConfigured.value || frameworkSettingsOpen.value,
);

const closeFrameworkSettings = () => {
  frameworkSettingsOpen.value = false;
  frameworkFormOpen.value = false;
  frameworkToken.value = "";
};

const connectChat = () => {
  chatService?.disconnect();
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
};

const handleFrameworkConfigure = async () => {
  if (!frameworkUrl.value.trim() || !frameworkToken.value) {
    message.warning(t("chat.frameworkRequired"));
    return;
  }

  frameworkSaving.value = true;
  try {
    await configureAgentFramework({
      framework: selectedFrameworkId.value,
      url: frameworkUrl.value.trim(),
      token: frameworkToken.value,
    });
    frameworkToken.value = "";
    frameworkConfigured.value = true;
    closeFrameworkSettings();
    connectChat();
  } catch {
    message.error(t("chat.frameworkConfigureFailed"));
  } finally {
    frameworkSaving.value = false;
  }
};

const hasMessages = computed(() => messagesList.value.length > 0);
const routeSessionKey = computed(() => {
  return route.query.session || "";
});
const routeSourceId = computed(() => {
  return typeof route.query.source_id === "string" ? route.query.source_id : "";
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
const quickActions = computed(() => [
  t("chat.capability1"),
  t("chat.capability2"),
  t("chat.capability3"),
]);
const selectedSessionLabel = computed(() => {
  if (!selectedSessionKey.value) {
    return "";
  }

  const matchedSession = sessions.value.find(
    (session) => session.key === selectedSessionKey.value,
  );

  return matchedSession?.key || "";
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

const buildAgentGroupLabel = (group: ChatSessionGroup) => {
  return group.agentId === "ungrouped"
    ? group.displayName
    : `agent:${group.agentId}`;
};

const buildSessionDropdownLabel = (session: ChatSessionSummary) => {
  const label = session.displayName || session.key;
  const agentPrefix = session.agentId ? `agent:${session.agentId}:` : "";

  return agentPrefix && label.startsWith(agentPrefix)
    ? label.slice(agentPrefix.length)
    : label;
};

const resolvePreferredSessionKeyForSource = () => {
  const mappedAgentName = SOURCE_AGENT_NAME_MAP[routeSourceId.value];

  if (mappedAgentName) {
    const matchedGroup = displaySessionGroups.value.find(
      (group) =>
        group.agentId === mappedAgentName ||
        group.displayName === mappedAgentName,
    );

    if (matchedGroup?.sessions[0]?.key) {
      return matchedGroup.sessions[0].key;
    }
  }

  return sessions.value[0]?.key || "";
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
  await updateRouteSession(sessionKey);
  chatService?.selectSession(sessionKey);
  scrollToBottom();
};

const syncSessionFromRoute = async () => {
  if (!sessions.value.length) {
    selectedSessionKey.value = "";
    return;
  }

  const preferredSessionKey = resolvePreferredSessionKeyForSource();
  const shouldAutoSwitchBySourceChange =
    Boolean(routeSourceId.value) &&
    routeSourceId.value !== lastAutoSelectedSourceId;

  if (shouldAutoSwitchBySourceChange && preferredSessionKey) {
    lastAutoSelectedSourceId = routeSourceId.value;

    if (
      selectedSessionKey.value === preferredSessionKey &&
      routeSessionKey.value === preferredSessionKey
    ) {
      return;
    }

    await applySessionSelection(preferredSessionKey);
    return;
  }

  const matchedSession = sessions.value.find(
    (session) => session.key === routeSessionKey.value,
  );
  const nextSessionKey = matchedSession?.key || preferredSessionKey;

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

const handleEnterPress = () => {
  handleSendMessage();
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
  handleSendMessage();
};

const handleQuickAction = (question: string) => {
  handleSendFollowup(question);
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

  void applySessionSelection(sessionKey);
};

const handleRefreshHistory = async () => {
  if (!chatService || isHistoryLoading.value || isStreaming.value) {
    return;
  }

  await chatService.refreshHistory();
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
  [sessions, sessionGroups, routeSessionKey, routeSourceId],
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

onUnmounted(() => {
  chatService?.disconnect();

  if (scrollContainer.value && throttledHandleScroll) {
    scrollContainer.value.removeEventListener("scroll", throttledHandleScroll);
  }

  resizeObserverRef.value?.disconnect();
});

onMounted(async () => {
  try {
    const config = await getDashboardConfig();
    agentFrameworks.value = config.frameworks || [];
    const defaultFramework = agentFrameworks.value[0];
    if (defaultFramework) {
      selectedFrameworkId.value = defaultFramework.id;
      frameworkUrl.value = defaultFramework.defaultUrl;
    }
    if (config.chat === "configured") {
      frameworkConfigured.value = true;
      connectChat();
    }
  } catch {
    frameworkConfigured.value = false;
    message.error(t("chat.frameworkConfigLoadFailed"));
  }
});
</script>

<style scoped lang="less">
.chat-container {
  height: 100%;
  background: var(--surface-panel-bg);
}

.chat-header {
  .flex-between;
  flex-wrap: wrap;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-main-color);
  background: var(--surface-glass-bg);
  backdrop-filter: blur(12px);

  .header-left {
    gap: 14px;
  }

  .assistant-copy {
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
    display: flex;
    align-items: center;

    .badge-icon {
      font-size: 20px;
      height: 38px;
      width: 38px;
      color: var(--color-white);
      background: var(--color-primary);
      border-radius: 12px;
      box-shadow: 0 8px 16px var(--bg-box-shadow);
      .vertical-center;
    }
  }

  .header-right {
    gap: 10px;
    min-width: 0;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .header-status {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 34px;
    height: 34px;
    border-radius: 999px;
    border: 1px solid var(--border-primary);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;

    &.connected {
      background: var(--color-successBg);
      color: var(--color-success);
      border-color: var(--border-success);
    }

    &.connecting {
      background: var(--color-warningBg);
      color: var(--color-warning);
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

.framework-form {
  gap: 18px;
  padding-top: 4px;
}

.framework-card {
  flex-shrink: 0;
  margin: 16px 20px 0;
  padding: 16px;
  gap: 12px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--surface-panel-bg);
}

.framework-card-copy {
  gap: 4px;
}

.framework-card-title {
  color: var(--font-main-color);
  font-size: var(--font-size-14);
  font-weight: 700;
}

.framework-card-description,
.framework-supported-label {
  color: var(--font-info-color);
  font-size: var(--font-size-12);
}

.framework-card-close {
  flex: 0 0 auto;
  border: 0;
  background: transparent;
  color: var(--font-tip-color);
  cursor: pointer;
  font-size: 20px;
  line-height: 1;
}

.framework-field {
  gap: 8px;

  label {
    color: var(--font-main-color);
    font-weight: 600;
  }
}

.framework-options {
  gap: 8px;
}

.framework-option {
  padding: 7px 14px;
  border: 1px solid var(--border-primary);
  border-radius: 6px;
  background: var(--surface-panel-bg);
  color: var(--font-main-color);
  cursor: pointer;

  &.active {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }
}

.framework-cache-note {
  color: var(--font-tip-color);
  font-size: var(--font-size-12);
}

.framework-actions {
  gap: 8px;
}

@keyframes chat-refresh-spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

.toolbar-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--font-info-color);
  cursor: pointer;

  &:disabled {
    cursor: default;
    opacity: 0.6;
  }

  &.spinning {
    animation: chat-refresh-spin 0.9s linear infinite;
  }
}

.session-history-panel {
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
    border-color: var(--color-primary);
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
  background: var(--color-primary);
  color: var(--color-white);
  font-size: 11px;
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

  &.has-framework-card .chat-content.full-height {
    height: auto;
  }
}

.chat-content {
  width: 100%;
  align-items: center;
  gap: 32px;
  flex-shrink: 0;
  max-width: 100%;
  overflow: hidden;

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
  width: 100%;
  max-width: 960px;
  flex-shrink: 0;

  .welcome-card {
    text-align: left;
    padding: 22px;
  }

  .welcome-eyebrow {
    font-size: var(--font-size-12);
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--color-primary);
  }

  .tip-wrap {
    margin-top: 12px;
    max-width: 680px;
    font-size: var(--font-size-14);
    line-height: 1.6;
    color: var(--font-text-color);
    gap: 6px;

    .bulb-icon {
      font-size: 14px;
      color: var(--color-primary);
    }
  }

  .session-loading-tip {
    margin-top: 12px;
    font-size: var(--font-size-12);
    color: var(--font-tip-color);
  }

  .capability-list {
    margin-top: 16px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .capability-chip {
    padding: 8px 12px;
    border-radius: 999px;
    background: var(--color-primaryBg);
    border: 1px solid var(--border-primary);
    color: var(--font-main-color);
    font-size: var(--font-size-12);
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      background: var(--surface-card-bg-hover);
      border-color: var(--color-primary);
      color: var(--color-primary-hover);
    }
  }
}

.input-wrap {
  width: 100%;
  max-width: 960px;
  position: relative;
  box-sizing: border-box;
  padding: 0 24px;
  flex-shrink: 0;

  .bottom-wrap {
    position: absolute;
    top: -40px;
    width: 100%;
    height: 32px;
    .to-bottom {
      position: fixed;
      width: 32px;
      height: 32px;
      cursor: pointer;
      z-index: 20;
      border-radius: 50%;
      background-color: var(--bg-card-color);
      border: 1px solid var(--border-main-color);
      box-shadow: 0px 2px 4px 0px var(--bg-box-shadow);

      &:hover {
        background-color: var(--color-primaryBg);
        border: 1px solid var(--color-primary);

        .anticon-arrow-down {
          color: var(--color-primary);
        }
      }
    }
  }
}

.input-container {
  width: 100%;
  border: 1px solid var(--border-primary);
  border-radius: 22px;
  background: var(--surface-card-bg);
  padding: 12px 14px 8px 14px;
  gap: 8px;
  transition: all 0.2s;
  box-shadow: 0 14px 28px var(--bg-box-shadow);

  &:focus-within {
    border-color: var(--color-primary);
    box-shadow: 0 18px 34px var(--bg-box-shadow);
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

.input-footer {
  width: 100%;
  gap: 8px;
  flex-wrap: wrap;
}

.footer-right {
  gap: 12px;
  flex-shrink: 0;
}

.new-session-btn {
  height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  border-color: var(--border-primary);
  background: var(--surface-panel-bg);
  color: var(--font-main-color);
  font-size: var(--font-size-12);
  font-weight: 600;
  box-shadow: 0 6px 14px
    color-mix(in srgb, var(--bg-box-shadow) 42%, transparent);

  &:hover,
  &:focus {
    border-color: var(--color-primary);
    color: var(--color-primary-hover);
    background: var(--surface-card-bg-hover);
  }
}
.common-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
  background: var(--color-primaryBg);
  border: 1px solid var(--border-primary);

  &:hover {
    background: var(--surface-card-bg-hover);
    border-color: var(--color-primary);
  }
}

.divider {
  width: 1px;
  height: 18px;
  background: var(--border-primary);
}

.action-btn {
  width: 36px;
  min-width: 36px !important;
  height: 36px;
  border: none;
  background: var(--color-primary);
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

    .selected-session-pill {
      flex: 1 1 100%;
      white-space: normal;
      overflow-wrap: anywhere;
    }
  }

  .message-box .intel-markdown {
    width: 100%;
    padding: 0 12px;
  }

  .initial-input .welcome-card {
    padding: 18px 16px;
  }

  .input-wrap {
    padding: 0 12px;
  }
}
.selected-session-pill {
  flex: 0 0 auto;
  width: max-content;
  padding: 7px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-primary);
  background: color-mix(in srgb, var(--surface-card-bg) 88%, transparent);
  color: var(--font-main-color);
  font-size: var(--font-size-12);
  font-weight: 600;
  line-height: 1.2;
  white-space: nowrap;
}
</style>
