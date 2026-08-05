<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="message-item">
    <div v-if="message.role === 'user'" class="question-container">
      <div class="question-content">
        <div class="content">{{ message.content }}</div>
        <div v-if="userHasMeta" class="message-meta message-meta-user">
          <span class="message-meta-speaker">
            {{ t("chat.youLabel") }}
          </span>
          <span v-if="userMetaText" class="message-meta-inline-value">
            {{ userMetaText }}
          </span>
        </div>
      </div>
    </div>

    <div v-else class="assistant-response-block">
      <div
        v-if="
          message.messageKind === 'assistant-agent-run' && displayAgents.length
        "
        class="assistant-answer-shell"
      >
        <div class="answer-container agent-answer-container">
          <span class="answer-badge">
            <SvgIcon name="icon-chatbot1" inherit
          /></span>
          <div class="agent-card-list flex-column">
            <div
              v-for="agent in displayAgents"
              :key="agent.id"
              class="agent-card"
              :class="{ 'has-tool': agent.hasTool }"
            >
              <div v-if="agent.hasTool" class="agent-tool-corner">
                <ToolOutlined />
              </div>
              <div class="agent-card-head flex-left">
                <SvgIcon
                  name="icon-agent"
                  :size="12"
                  :style="{ color: 'var(--color-primary)' }"
                />
                {{ $t("chat.agentLabel") }}
              </div>
              <div
                v-for="segment in agent.segments"
                :key="segment.id"
                class="agent-stream-block"
                :class="segment.stream"
              >
                <template v-if="isToolSegment(segment)">
                  <div class="tool-output-card live-tool-block">
                    <div class="tool-output-header">
                      <div class="tool-output-copy">
                        <div class="tool-output-title-row flex-left">
                          <span class="tool-inline-icon">
                            <ToolOutlined />
                          </span>
                          <span class="tool-output-title">
                            {{
                              translateKnownToolTitle(segment.title) ||
                              t("chat.toolTitle")
                            }}:
                          </span>
                          <span
                            v-if="segment.subtitle"
                            class="tool-output-subtitle"
                          >
                            {{ segment.subtitle }}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div
                      v-show="
                        !isSegmentCollapsed(segment.id) && segment.content
                      "
                      class="tool-output-body answer-content"
                      v-html="renderToolContent(segment.content)"
                      @click="handleContentClick"
                    ></div>
                    <button
                      type="button"
                      class="tool-toggle-btn live-tool-toggle-btn"
                      @click="toggleSegmentCollapse(segment.id)"
                    >
                      <CaretDownOutlined
                        :class="{ collapsed: isSegmentCollapsed(segment.id) }"
                      />
                    </button>
                  </div>
                </template>
                <template v-else>
                  <div class="tool-output-header">
                    <div class="agent-stream-title">
                      {{ $t("chat.assistantStream") }}
                    </div>
                  </div>
                  <div
                    v-if="segment.content"
                    class="answer-content"
                    v-html="renderMarked(segment.content)"
                    @click="handleContentClick"
                  ></div>
                </template>
              </div>
              <div v-if="!agent.isComplete" class="agent-loading">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        </div>
        <div
          v-if="assistantHasMeta"
          class="message-meta message-meta-assistant"
        >
          <span class="message-meta-speaker-icon" aria-hidden="true">
            <SvgIcon name="icon-chatbot1" inherit />
          </span>
          <span class="message-meta-speaker message-meta-speaker-assistant">
            {{ t("chat.assistantMetaLabel") }}
          </span>
          <span v-if="assistantMetaTime" class="message-meta-chip">
            {{ assistantMetaTime }}
          </span>
          <span v-if="assistantMetaModel" class="message-meta-chip model">
            {{ assistantMetaModel }}
          </span>
        </div>
      </div>

      <div v-else class="assistant-answer-shell">
        <div class="answer-container" :class="containerClassName">
          <span class="answer-badge" :class="{ tool: isOuterToolBadge }">
            <ToolOutlined v-if="isOuterToolBadge" />
            <span v-else> <SvgIcon name="icon-chatbot1" inherit /></span>
          </span>

          <div class="mixed-content-list">
            <template v-for="block in displayBlocks" :key="block.id">
              <div
                v-if="block.kind === 'text'"
                class="answer-content mixed-text-block"
                v-html="renderMarked(block.content)"
                @click="handleContentClick"
              ></div>

              <div
                v-else-if="block.kind === 'thinking'"
                class="thinking-output-card inline-thinking-block"
              >
                <div class="thinking-output-header">
                  <div class="thinking-output-copy">
                    <div class="thinking-output-title-row flex-left">
                      <span class="thinking-inline-icon">
                        <BulbOutlined />
                      </span>
                      <span class="thinking-output-title">
                        {{
                          translateKnownToolTitle(block.title) ||
                          t("chat.thinkingTitle")
                        }}
                      </span>
                      <span
                        v-if="block.subtitle"
                        class="thinking-output-subtitle"
                      >
                        {{ block.subtitle }}
                      </span>
                    </div>
                  </div>
                  <button
                    v-if="block.collapsible"
                    type="button"
                    class="tool-toggle-btn thinking-toggle-btn"
                    @click="toggleBlockCollapse(block.id)"
                  >
                    <CaretDownOutlined
                      :class="{ collapsed: isBlockCollapsed(block.id) }"
                    />
                  </button>
                </div>
                <div
                  v-show="!isBlockCollapsed(block.id)"
                  class="thinking-output-body answer-content"
                  v-html="renderMarked(block.content)"
                  @click="handleContentClick"
                ></div>
              </div>

              <div v-else class="tool-output-card inline-tool-block">
                <div class="tool-output-header">
                  <div class="tool-output-copy">
                    <div class="tool-output-title-row flex-left">
                      <span class="tool-inline-icon">
                        <ToolOutlined />
                      </span>
                      <span class="tool-output-title">
                        {{
                          translateKnownToolTitle(block.title) ||
                          t("chat.toolTitle")
                        }}
                      </span>
                      <span v-if="block.subtitle" class="tool-output-subtitle">
                        {{ block.subtitle }}
                      </span>
                    </div>
                  </div>
                  <button
                    v-if="block.collapsible"
                    type="button"
                    class="tool-toggle-btn"
                    @click="toggleBlockCollapse(block.id)"
                  >
                    <CaretDownOutlined
                      :class="{ collapsed: isBlockCollapsed(block.id) }"
                    />
                  </button>
                </div>
                <div
                  v-show="!isBlockCollapsed(block.id)"
                  class="tool-output-body answer-content"
                  v-html="renderToolContent(block.content)"
                  @click="handleContentClick"
                ></div>
              </div>
            </template>
          </div>
        </div>
        <div
          v-if="assistantHasMeta"
          class="message-meta message-meta-assistant"
        >
          <span class="message-meta-speaker flex-left">
            <span class="message-meta-speaker-icon"> ✦ </span>
            {{ t("chat.assistantMetaLabel") }}
          </span>
          <span v-if="assistantMetaTime" class="message-meta-chip">
            {{ assistantMetaTime }}
          </span>
          <span v-if="assistantMetaModel" class="message-meta-chip model">
            {{ assistantMetaModel }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import CustomRenderer from "@/utils/customRenderer";
import type { ChatMessageBlock, ChatMessageView } from "./WebSocketChatService";
import {
  BulbOutlined,
  CaretDownOutlined,
  ToolOutlined,
} from "@ant-design/icons-vue";
import "highlight.js/styles/atom-one-dark.css";
import { marked } from "marked";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{
  message: ChatMessageView;
  messageIndex: number | null;
  lastQuery?: boolean;
  lastResponse?: boolean;
  isStreaming?: boolean;
}>();

const emit = defineEmits(["send-question", "preview"]);
const { t } = useI18n();

marked.setOptions({
  pedantic: false,
  gfm: true,
  breaks: false,
  renderer: CustomRenderer,
});

const collapsedBlockState = ref<Record<string, boolean>>({});

const displayAgents = computed<ChatMessageView["agents"]>(() => {
  return Array.isArray(props.message.agents) ? props.message.agents : [];
});

const displayBlocks = computed<ChatMessageBlock[]>(() => {
  if (
    Array.isArray(props.message.contentBlocks) &&
    props.message.contentBlocks.length
  ) {
    return props.message.contentBlocks;
  }

  if (
    props.message.messageKind === "tool-result" ||
    props.message.messageKind === "assistant-tool-call"
  ) {
    return [
      {
        id: `${props.message.id}-tool`,
        kind:
          props.message.messageKind === "tool-result"
            ? "tool-result"
            : "tool-call",
        content: props.message.content || "",
        title: props.message.title || "",
        subtitle: props.message.subtitle || "",
        showToolIcon: true,
        collapsible: props.message.collapsible,
        startsCollapsed: props.message.startsCollapsed,
      },
    ];
  }

  return [
    {
      id: `${props.message.id}-text`,
      kind: "text",
      content: props.message.content || "",
      title: "",
      subtitle: "",
      showToolIcon: false,
      collapsible: false,
      startsCollapsed: false,
    },
  ];
});

const isToolLikeBlock = (block: ChatMessageBlock) => {
  return block.kind === "tool-call" || block.kind === "tool-result";
};

const containerClassName = computed(() => ({
  "tool-answer-container":
    displayBlocks.value.length > 0 &&
    displayBlocks.value.every((block) => isToolLikeBlock(block)),
}));

const isOuterToolBadge = computed(() => {
  return (
    displayBlocks.value.length > 0 &&
    displayBlocks.value.every((block) => isToolLikeBlock(block))
  );
});

const formatMessageTime = (timestamp?: number) => {
  if (!timestamp || !Number.isFinite(timestamp)) {
    return "";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(timestamp));
};

const formatModelName = (model?: string) => {
  if (!model) {
    return "";
  }

  const normalizedModel = model.trim();
  if (!normalizedModel) {
    return "";
  }

  const modelSegments = normalizedModel.split("/").filter(Boolean);
  return modelSegments[modelSegments.length - 1] || normalizedModel;
};

const userMetaText = computed(() => {
  if (props.message.role !== "user") {
    return "";
  }

  return formatMessageTime(props.message.timestamp);
});

const userHasMeta = computed(() => {
  return props.message.role === "user" && Boolean(userMetaText.value);
});

const assistantMetaTime = computed(() => {
  if (props.message.role !== "assistant") {
    return "";
  }

  return formatMessageTime(props.message.timestamp);
});

const assistantMetaModel = computed(() => {
  if (props.message.role !== "assistant") {
    return "";
  }

  return formatModelName(props.message.model);
});

const assistantHasMeta = computed(() => {
  if (props.message.role !== "assistant") {
    return false;
  }

  return Boolean(assistantMetaTime.value || assistantMetaModel.value);
});

watch(
  () => [props.message.id, props.message.contentBlocks],
  () => {
    const nextState: Record<string, boolean> = {};
    displayBlocks.value.forEach((block) => {
      nextState[block.id] = Boolean(block.startsCollapsed);
    });
    collapsedBlockState.value = nextState;
  },
  { immediate: true },
);

watch(
  () => props.message.agents,
  (agents) => {
    const nextState = { ...collapsedBlockState.value };
    (agents || []).forEach((agent) => {
      agent.segments.forEach((segment) => {
        if (segment.stream === "tool" && !(segment.id in nextState)) {
          nextState[segment.id] = false;
        }
      });
    });
    collapsedBlockState.value = nextState;
  },
  { immediate: true, deep: true },
);

const renderMarked = (content: string) => marked(content || "");

const translateKnownToolTitle = (title: string) => {
  const normalizedTitle = title.trim().toLowerCase();

  if (!normalizedTitle) {
    return "";
  }

  if (normalizedTitle === "tool") {
    return t("chat.toolCallTitle");
  }

  if (normalizedTitle === "tool output") {
    return t("chat.toolOutputTitle");
  }

  if (normalizedTitle === "thinking") {
    return t("chat.thinkingTitle");
  }

  return title;
};

const renderToolContent = (content: string) => {
  const parsedJson = parseJsonString(content);
  if (parsedJson !== null) {
    return `<pre class="tool-json-block"><code>${escapeHtml(
      JSON.stringify(parsedJson, null, 2),
    )}</code></pre>`;
  }

  return renderMarked(content);
};

const parseJsonString = (content: string) => {
  const trimmedContent = content.trim();
  if (!trimmedContent) {
    return null;
  }

  try {
    return JSON.parse(trimmedContent);
  } catch {
    return null;
  }
};

const escapeHtml = (content: string) => {
  return content
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
};

const isBlockCollapsed = (blockId: string) => {
  return Boolean(collapsedBlockState.value[blockId]);
};

const isToolSegment = (
  segment: ChatMessageView["agents"][number]["segments"][number],
) => {
  return segment.stream === "tool";
};

const isSegmentCollapsed = (segmentId: string) => {
  return Boolean(collapsedBlockState.value[segmentId]);
};

const toggleBlockCollapse = (blockId: string) => {
  collapsedBlockState.value = {
    ...collapsedBlockState.value,
    [blockId]: !collapsedBlockState.value[blockId],
  };
};

const toggleSegmentCollapse = (segmentId: string) => {
  collapsedBlockState.value = {
    ...collapsedBlockState.value,
    [segmentId]: !collapsedBlockState.value[segmentId],
  };
};

const handleContentClick = (event: MouseEvent) => {
  const target = event.target as HTMLElement | null;
  if (!target || target.tagName.toLowerCase() !== "img") {
    return;
  }

  emit("preview", (target as HTMLImageElement).src);
};
</script>

<style scoped lang="less">
.message-item {
  position: relative;
  width: 100%;
  margin-bottom: 20px;
}

.assistant-response-block {
  .flex-column;
  gap: 12px;
}

.assistant-answer-shell {
  position: relative;
  padding-bottom: 28px;
}

.question-container {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  margin-bottom: 16px;

  .question-content {
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    font-size: var(--font-size-16);

    .content {
      width: auto;
      min-height: 36px;
      padding: 12px 16px;
      border-radius: 6px;
      line-height: 1.375;
      background-color: var(--message-bg);
    }
  }
}

.message-meta {
  margin-top: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: var(--font-size-11);
  line-height: 1.2;
  color: var(--font-tip-color);
}

.message-meta-speaker {
  font-weight: 700;
  color: var(--font-text-color);
}

.message-meta-speaker-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  font-size: 18px;
  margin-right: 2px;
}

.message-meta-inline-value {
  color: var(--font-tip-color);
}

.message-meta-chip {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 4px;
  color: var(--font-tip-color);
  font-size: var(--font-size-11);
  font-weight: 600;
}

.message-meta-chip.model {
  color: color-mix(
    in srgb,
    var(--color-primary-hover) 58%,
    var(--font-tip-color) 42%
  );
}

.message-meta-user {
  justify-content: flex-end;
  text-align: right;
  padding-right: 2px;
}

.message-meta-assistant {
  position: absolute;
  left: 0;
  bottom: 0;
  margin-top: 0;
  text-align: left;
}

.answer-container {
  position: relative;
  border-radius: 12px;
  padding: 16px 16px 14px 16px;
  background-color: var(--bg-content-color);
  box-shadow: 0 1px 3px var(--bg-box-shadow);

  .answer-badge {
    position: absolute;
    top: 0;
    left: -40px;
    width: 28px;
    height: 28px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    background: var(--color-primary);
    box-shadow: 0 8px 16px var(--bg-box-shadow);
    font-size: 16px;
    line-height: 1;
    color: var(--color-white);

    &.tool {
      background: color-mix(
        in srgb,
        var(--color-warning) 86%,
        var(--color-warningBg)
      );
      color: var(--color-white);
    }
  }

  .answer-content {
    margin-bottom: 0;
    font-size: var(--font-size-14);
    line-height: 1.6;
    word-wrap: break-word;
  }
}

.tool-answer-container {
  border: 1px solid var(--border-warning);
  background: color-mix(
    in srgb,
    var(--color-warningBg) 68%,
    var(--surface-card-bg) 32%
  );
  padding: 12px 16px;
}

.mixed-content-list {
  .flex-column;
  gap: 12px;
}

.mixed-text-block {
  margin-bottom: 0;
}

.tool-output-card,
.thinking-output-card {
  .flex-column;
  gap: 8px;
}

.inline-tool-block {
  padding: 8px 10px;
  border: 1px solid var(--border-primary);
  border-radius: 10px;
  background: color-mix(
    in srgb,
    var(--color-primaryBg) 28%,
    var(--surface-card-bg) 72%
  );
}

.inline-thinking-block {
  padding: 8px 10px;
  border: 1px solid var(--border-primary);
  border-radius: 10px;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--color-primary) 12%, transparent),
    color-mix(in srgb, var(--color-primaryBg) 72%, transparent)
  );
}

.tool-output-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.thinking-output-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.tool-output-copy {
  flex: 1;
  min-width: 0;
}

.thinking-output-copy {
  flex: 1;
  min-width: 0;
}

.tool-output-title-row,
.thinking-output-title-row {
  gap: 6px;
  flex-wrap: wrap;
}

.tool-inline-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  background: var(--surface-panel-bg);
  color: color-mix(in srgb, var(--color-warning) 88%, var(--font-main-color));
  font-size: 12px;
}

.thinking-inline-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  background: var(--surface-glass-bg);
  color: var(--color-primary);
  font-size: 12px;
}

.tool-output-title {
  font-size: var(--font-size-13);
  font-weight: 700;
  color: var(--font-main-color);
}

.thinking-output-title {
  font-size: var(--font-size-13);
  font-weight: 700;
  color: var(--color-primary);
}

.tool-output-subtitle {
  font-size: var(--font-size-11);
  color: var(--font-tip-color);
  word-break: break-word;
}

.thinking-output-subtitle {
  font-size: var(--font-size-11);
  color: color-mix(in srgb, var(--color-primary) 78%, var(--font-main-color));
  word-break: break-word;
}

.tool-toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--border-warning);
  border-radius: 999px;
  background: var(--surface-panel-bg);
  color: var(--font-main-color);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: color-mix(
      in srgb,
      var(--color-warning) 82%,
      var(--border-warning)
    );
    color: color-mix(in srgb, var(--color-warning) 88%, var(--font-main-color));
  }

  .collapsed {
    transform: rotate(-90deg);
  }
}

.thinking-toggle-btn {
  border-color: var(--border-primary);
  background: var(--surface-glass-bg);
  color: var(--color-primary);

  &:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
  }
}

.tool-output-body {
  padding: 8px 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--surface-panel-bg) 78%, transparent);
}

.thinking-output-body {
  padding: 8px 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--color-white) 54%, transparent);
}

:deep(.tool-json-block) {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: var(--font-size-12);
  line-height: 1.5;
}

:deep(.tool-json-block code) {
  display: block;
  white-space: inherit;
  font-family: inherit;
}

.agent-answer-container,
.agent-card-list {
  .flex-column;
  gap: 10px;
}

.agent-card {
  position: relative;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-primary);
  background: var(--surface-card-bg);
}

.agent-card.has-tool {
  border-color: var(--border-warning);
  background: color-mix(
    in srgb,
    var(--color-warningBg) 52%,
    var(--surface-card-bg) 48%
  );
}

.agent-tool-corner {
  position: absolute;
  top: 8px;
  left: 6px;
  width: 22px;
  height: 22px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-panel-bg);
  color: color-mix(in srgb, var(--color-warning) 88%, var(--font-main-color));
  box-shadow: 0 6px 14px var(--bg-box-shadow);
}

.agent-card-head {
  font-size: var(--font-size-12);
  font-weight: 700;
  color: var(--font-main-color);
  gap: 6px;
}

.agent-stream-block {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-panel-bg);
}

.agent-stream-block.tool {
  border: 1px solid var(--border-warning);
  background: var(--surface-card-bg-hover);
}

.live-tool-block {
  gap: 8px;
  position: relative;
}

.live-tool-toggle-btn {
  position: absolute;
  top: -2px;
  right: 8px;
}

.agent-stream-title {
  margin-bottom: 6px;
  font-size: var(--font-size-11);
  font-weight: 700;
  color: var(--font-tip-color);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.agent-loading {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 10px;
}

.agent-loading span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: blink 1.2s infinite ease-in-out;
}

.agent-loading span:nth-child(2) {
  animation-delay: 0.15s;
}

.agent-loading span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes blink {
  0% {
    opacity: 0.2;
  }

  20% {
    opacity: 1;
  }

  100% {
    opacity: 0.2;
  }
}
</style>
