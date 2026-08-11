<!--
  Copyright (C) 2026 Intel Corporation
  SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="message-item">
    <div v-if="message.role === 'user'" class="question-container">
      <div class="question-content">
        <div class="content" v-html="renderMarked(message.content)"></div>
      </div>
    </div>

    <div v-else class="assistant-response-block">
      <div
        v-if="
          message.messageKind === 'assistant-agent-run' && displayAgents.length
        "
        class="answer-container agent-answer-container"
      >
        <span class="answer-badge">
          <SvgIcon
            name="icon-chatbot1"
            :size="16"
            :style="{ color: 'var(--color-white)' }"
          />
        </span>
        <div class="agent-card-list">
          <div
            v-for="agent in displayAgents"
            :key="agent.id"
            class="agent-card"
            :class="getAgentCardClass(agent)"
          >
            <div v-if="agent.hasTool" class="agent-tool-corner">
              <ToolOutlined />
            </div>
            <div class="agent-card-head">
              <div class="agent-card-head-main">
                <span class="agent-card-icon" :class="agent.agentLevel">
                  <SvgIcon
                    :name="getAgentIconName(agent)"
                    :size="12"
                    :style="getAgentIconStyle(agent)"
                  />
                </span>
                <span>{{ getAgentLabel(agent) }}</span>
              </div>
            </div>
            <div
              v-for="segment in agent.segments"
              :key="segment.id"
              class="agent-stream-block"
              :class="segment.stream"
            >
              <template v-if="isToolSegment(segment)">
                <div class="tool-output-card live-tool-block">
                  <div
                    v-if="showSubAgentToolSegmentHeader()"
                    class="tool-output-header"
                  >
                    <div class="tool-output-copy">
                      <div class="tool-output-title-row">
                        <span class="tool-inline-icon">
                          <ToolOutlined />
                        </span>
                        <span class="tool-output-title">
                          {{ getToolSegmentTitle(segment.title) }}:
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
                    v-show="!isSegmentCollapsed(segment.id) && segment.content"
                    class="tool-output-body answer-content"
                    v-html="renderToolContent(segment.content)"
                    @click="handleContentClick"
                  ></div>
                  <button
                    v-if="!isSubAgent(agent)"
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
            <div v-if="isStreaming && !agent.isComplete" class="agent-loading">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
        <div
          v-if="displayErrorBlocks.length"
          class="mixed-content-list agent-error-list"
        >
          <template v-for="block in displayErrorBlocks" :key="block.id">
            <div class="error-output-card inline-error-block">
              <div class="error-output-header">
                <div class="error-output-copy">
                  <div class="error-output-title-row">
                    <span class="error-inline-icon">
                      <CloseCircleOutlined />
                    </span>
                    <span class="error-output-title">
                      {{ getErrorBlockTitle(block) }}
                    </span>
                    <span v-if="block.subtitle" class="error-output-subtitle">
                      {{ block.subtitle }}
                    </span>
                  </div>
                </div>
              </div>
              <div
                class="error-output-body answer-content"
                v-html="renderMarked(block.content)"
                @click="handleContentClick"
              ></div>
            </div>
          </template>
        </div>
      </div>

      <div v-else class="answer-container" :class="containerClassName">
        <span class="answer-badge" :class="{ tool: isOuterToolBadge }">
          <ToolOutlined v-if="isOuterToolBadge" />
          <span v-else>
            <SvgIcon
              name="icon-chatbot1"
              :size="16"
              :style="{ color: 'var(--color-white)' }"
          /></span>
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
                  <div class="thinking-output-title-row">
                    <span class="thinking-inline-icon">
                      <BulbOutlined />
                    </span>
                    <span class="thinking-output-title">
                      {{ getThinkingBlockTitle(block) }}
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

            <div
              v-else-if="block.kind === 'error'"
              class="error-output-card inline-error-block"
            >
              <div class="error-output-header">
                <div class="error-output-copy">
                  <div class="error-output-title-row">
                    <span class="error-inline-icon">
                      <CloseCircleOutlined />
                    </span>
                    <span class="error-output-title">
                      {{ getErrorBlockTitle(block) }}
                    </span>
                    <span v-if="block.subtitle" class="error-output-subtitle">
                      {{ block.subtitle }}
                    </span>
                  </div>
                </div>
              </div>
              <div
                class="error-output-body answer-content"
                v-html="renderMarked(block.content)"
                @click="handleContentClick"
              ></div>
            </div>

            <div v-else class="tool-output-card inline-tool-block">
              <div class="tool-output-header">
                <div class="tool-output-copy">
                  <div class="tool-output-title-row">
                    <span class="tool-inline-icon">
                      <ToolOutlined />
                    </span>
                    <span class="tool-output-title">
                      {{ getToolBlockTitle(block) }}
                    </span>
                    <span v-if="block.subtitle" class="tool-output-subtitle">
                      {{ block.subtitle }}
                    </span>
                    <span v-if="block.tag" class="tool-output-tag">
                      {{ block.tag }}
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
    </div>
  </div>
</template>

<script setup lang="ts">
import CustomRenderer from "@/utils/customRenderer";
import type {
  ChatAgentRun,
  ChatMessageBlock,
  ChatMessageView,
} from "./WebSocketChatService";
import {
  BulbOutlined,
  CaretDownOutlined,
  CloseCircleOutlined,
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

const displayErrorBlocks = computed<ChatMessageBlock[]>(() => {
  return displayBlocks.value.filter((block) => block.kind === "error");
});

const isToolLikeBlock = (block: ChatMessageBlock) => {
  return block.kind === "tool-call" || block.kind === "tool-result";
};

const isSubAgent = (agent: ChatAgentRun) => {
  return agent.agentLevel === "sub";
};

const getAgentLabel = (agent: ChatAgentRun) => {
  return isSubAgent(agent) ? t("chat.subAgentLabel") : t("chat.agentLabel");
};

const getAgentIconName = (agent: ChatAgentRun) => {
  return isSubAgent(agent) ? "icon-subagent" : "icon-agent";
};

const getAgentIconStyle = (agent: ChatAgentRun) => {
  return {
    color: isSubAgent(agent) ? "var(--color-success)" : "var(--color-primary)",
  };
};

const getAgentCardClass = (agent: ChatAgentRun) => {
  return {
    "has-tool": agent.hasTool,
    "sub-agent-card": isSubAgent(agent),
  };
};

const translateKnownThinkingTitle = (title: string) => {
  const normalizedTitle = title.trim().toLowerCase();

  if (!normalizedTitle || normalizedTitle === "thinking") {
    return t("chat.thinkingTitle");
  }

  return title;
};

const translateKnownToolTitle = (title: string) => {
  const normalizedTitle = title.trim().toLowerCase();

  if (!normalizedTitle) {
    return "";
  }

  if (normalizedTitle === "tool") {
    return t("chat.toolCallTitle");
  }

  if (normalizedTitle === "tool output") {
    return t("chat.toolTitle");
  }

  return title;
};

const getToolSegmentTitle = (title: string) => {
  return translateKnownToolTitle(title) || t("chat.toolCallTitle");
};

const getToolBlockTitle = (block: ChatMessageBlock) => {
  const translatedTitle = translateKnownToolTitle(block.title || "");
  if (translatedTitle) {
    return translatedTitle;
  }

  return block.kind === "tool-result"
    ? t("chat.toolTitle")
    : t("chat.toolCallTitle");
};

const getThinkingBlockTitle = (block: ChatMessageBlock) => {
  return translateKnownThinkingTitle(block.title || "");
};

const getErrorBlockTitle = (block: ChatMessageBlock) => {
  const normalizedTitle = (block.title || "").trim().toLowerCase();
  if (!normalizedTitle || normalizedTitle === "error") {
    return t("common.error");
  }

  return block.title;
};

const showSubAgentToolSegmentHeader = () => {
  return true;
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

watch(
  () => [props.message.id, props.message.contentBlocks],
  () => {
    const nextState: Record<string, boolean> = {
      ...collapsedBlockState.value,
    };
    displayBlocks.value.forEach((block) => {
      if (!(block.id in nextState)) {
        nextState[block.id] = Boolean(block.startsCollapsed);
      }
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
        if (segment.stream !== "tool") {
          return;
        }

        if (isSubAgent(agent)) {
          nextState[segment.id] = false;
          return;
        }

        if (!(segment.id in nextState)) {
          nextState[segment.id] = true;
        }
      });
    });
    collapsedBlockState.value = nextState;
  },
  { immediate: true, deep: true },
);

const renderMarked = (content: string) => marked(content || "");

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
      line-height: 22px;
      background-color: var(--message-bg);
    }
  }
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
    background: var(--color-primary-second);
    box-shadow: 0 8px 16px var(--bg-box-shadow);
    font-size: var(--font-size-16);
    line-height: 1;

    &.tool {
      background: var(--color-warning-strong);
      color: var(--color-white);
    }
  }

  .answer-content {
    margin-bottom: 0;
    font-size: var(--font-size-14);
    line-height: 1.6;
    color: var(--font-text-color);
    word-wrap: break-word;
  }
}

.tool-answer-container {
  border: 1px solid var(--border-warning);
  background: var(--color-warningBg);
  padding: 12px 16px;
  margin-bottom: 8px;
}

.mixed-content-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mixed-text-block {
  margin-bottom: 0;
}

.tool-output-card {
  .flex-column;
  gap: 8px;
}

.thinking-output-card {
  .flex-column;
  gap: 8px;
}

.error-output-card {
  .flex-column;
  gap: 8px;
}

.inline-tool-block {
  padding: 8px 10px;
  border: 1px solid var(--border-warning);
  border-radius: 10px;
  background: color-mix(in srgb, var(--color-warningBg) 28%, transparent);
}

.inline-thinking-block {
  padding: 8px 10px;
  border: 1px solid var(--border-purple);
  border-radius: 10px;
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--color-purpleBg) 72%, transparent),
    color-mix(in srgb, var(--color-purpleBg) 48%, transparent)
  );
}

.inline-error-block {
  padding: 8px 10px;
  border: 1px solid color-mix(in srgb, var(--color-error) 42%, transparent);
  border-radius: 10px;
  background: color-mix(in srgb, var(--color-error) 10%, transparent);
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

.error-output-header {
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

.error-output-copy {
  flex: 1;
  min-width: 0;
}

.tool-output-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.thinking-output-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.error-output-title-row {
  display: flex;
  align-items: center;
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
  color: var(--color-warning-strong);
  font-size: var(--font-size-12);
}

.thinking-inline-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  background: var(--surface-glass-bg);
  color: var(--color-purple);
  font-size: var(--font-size-12);
}

.error-inline-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 6px;
  background: color-mix(
    in srgb,
    var(--color-error) 16%,
    var(--surface-panel-bg)
  );
  color: var(--color-error);
  font-size: var(--font-size-12);
}

.tool-output-title {
  font-size: var(--font-size-13);
  font-weight: 700;
  color: var(--font-main-color);
}

.thinking-output-title {
  font-size: var(--font-size-13);
  font-weight: 700;
  color: var(--color-purple);
}

.error-output-title {
  font-size: var(--font-size-13);
  font-weight: 700;
  color: var(--color-error);
}

.tool-output-subtitle {
  font-size: var(--font-size-11);
  color: var(--font-tip-color);
  word-break: break-word;
}

.tool-output-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  min-height: 16px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-successSoft) 72%, transparent);
  border: 1px solid var(--border-success);
  color: var(--color-success);
  font-size: var(--font-size-10);
  font-weight: 600;
  line-height: 1;
}

.thinking-output-subtitle {
  font-size: var(--font-size-11);
  color: color-mix(in srgb, var(--color-purple) 78%, var(--font-tip-color));
  word-break: break-word;
}

.error-output-subtitle {
  font-size: var(--font-size-11);
  color: color-mix(in srgb, var(--color-error) 78%, var(--font-tip-color));
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
  font-size: var(--font-size-12);
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--color-warning-strong);
    color: var(--color-warning-strong);
  }

  .collapsed {
    transform: rotate(-90deg);
  }
}

.thinking-toggle-btn {
  border-color: var(--border-purple);
  background: var(--surface-glass-bg);
  color: var(--color-purple);

  &:hover {
    border-color: var(--color-purple);
    color: var(--color-purple);
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
  background: color-mix(in srgb, var(--surface-glass-bg) 72%, transparent);
}

.error-output-body {
  padding: 8px 10px;
  border-radius: 8px;
  background: color-mix(
    in srgb,
    var(--color-error) 8%,
    var(--surface-panel-bg)
  );
}

.agent-error-list {
  margin-top: 10px;
}

:deep(.tool-json-block) {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: Consolas, "Courier New", monospace;
  font-size: var(--font-size-12);
  line-height: 1.5;
}

:deep(.tool-json-block code) {
  display: block;
  white-space: inherit;
  font-family: inherit;
}

.agent-answer-container {
  .flex-column;
  gap: 10px;
}

.agent-card-list {
  .flex-column;
  gap: 10px;
}

.agent-card {
  position: relative;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid var(--border-primary);
  background: var(--surface-card-bg);
}

.agent-card.sub-agent-card {
  border-color: var(--border-success);
  background: color-mix(
    in srgb,
    var(--color-successSoft) 72%,
    var(--surface-card-bg)
  );
}

.agent-card.has-tool {
  border-color: var(--color-warning);
  background: var(--color-warningBg);
}

.agent-card.sub-agent-card.has-tool {
  border-color: color-mix(
    in srgb,
    var(--border-success) 68%,
    var(--border-warning)
  );
  background: color-mix(
    in srgb,
    var(--color-successSoft) 62%,
    var(--color-warningBg)
  );
}

.agent-tool-corner {
  position: absolute;
  top: 10px;
  left: 12px;
  width: 22px;
  height: 22px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-panel-bg);
  color: var(--color-warning-strong);
  box-shadow: 0 6px 14px var(--bg-box-shadow);
}

.agent-card-head {
  .flex-between;
  gap: 10px;
  font-size: var(--font-size-12);
  font-weight: 700;
  color: var(--font-main-color);
}

.agent-card-head-main {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.agent-card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 7px;
  background: color-mix(
    in srgb,
    var(--color-primaryBg) 85%,
    var(--color-white)
  );
}

.agent-card-icon.sub {
  background: color-mix(
    in srgb,
    var(--color-successSoft) 82%,
    var(--color-white)
  );
}

.agent-card-name {
  font-size: var(--font-size-11);
  font-weight: 600;
  color: var(--font-tip-color);
  word-break: break-word;
  text-align: right;
}

.agent-stream-block {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--surface-panel-bg);
}

.agent-card.sub-agent-card .agent-stream-block {
  background: color-mix(
    in srgb,
    var(--color-successSoft) 64%,
    var(--surface-panel-bg)
  );
}

.agent-stream-block.tool {
  border: 1px solid var(--border-warning);
  background: var(--surface-card-bg-hover);
}

.agent-card.sub-agent-card .agent-stream-block.tool {
  border-color: color-mix(
    in srgb,
    var(--border-success) 60%,
    var(--border-warning)
  );
  background: color-mix(
    in srgb,
    var(--color-successSoft) 52%,
    var(--surface-card-bg-hover)
  );
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
  background: var(--color-primary-second);
  animation: blink 1.2s infinite ease-in-out;
}

.agent-card.sub-agent-card .agent-loading span {
  background: var(--color-success);
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
