<!--
  Copyright (C) 2026 Intel Corporation
  SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="knowledge-menu">
    <div class="menu-wrapper">
      <div class="menu-header">
        <div class="menu-title">{{ $t("knowledge.title") }}</div>
        <div class="menu-description">{{ $t("knowledge.description") }}</div>
      </div>

      <div
        v-for="(knowledge, index) in knowledgeList"
        :key="knowledge.idx"
        class="knowledge-card"
      >
        <div class="knowledge-header">
          <a-checkbox
            :checked="knowledge.active"
            @change="handleCheckChange(knowledge, $event.target.checked)"
          />
          <div class="knowledge-toggle" @click="toggleExpand(knowledge.idx)">
            <SvgIcon
              :name="
                isExpanded(knowledge.idx)
                  ? 'icon-folder-open'
                  : 'icon-folder-close'
              "
              :size="18"
              :style="{ color: 'var(--color-primary)' }"
            />
            <div class="knowledge-title-wrap">
              <div class="knowledge-title">{{ knowledge.name }}</div>
              <div class="knowledge-count">
                {{ $t("knowledge.total") }}:
                {{ knowledge.total }}
              </div>
            </div>
            <RightOutlined
              :class="['toggle-arrow', { open: isExpanded(knowledge.idx) }]"
            />
          </div>
        </div>

        <div v-if="isExpanded(knowledge.idx)" class="file-list">
          <div
            v-for="file in getVisibleFiles(knowledge)"
            :key="file.path"
            class="file-item"
            :class="{ 'active-file': selectedId === file.path }"
            :title="file.name"
          >
            <span class="file-dot"></span>
            <span class="file-name">{{ file.name }}</span>
          </div>
        </div>

        <div
          v-if="
            isExpanded(knowledge.idx) &&
            getFileCount(knowledge) > FILE_PREVIEW_COUNT
          "
          class="toggle-more"
          @click="toggleMore(knowledge.idx)"
        >
          {{
            isShowingAllFiles(knowledge.idx)
              ? $t("knowledge.collapse")
              : $t("knowledge.viewMore")
          }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import {
  getKnowledgeBaseList,
  requestKnowledgeBaseUpdate,
} from "@/api/knowledgeBase";
import SvgIcon from "@/components/SvgIcon.vue";
import { RightOutlined } from "@ant-design/icons-vue";

interface KnowledgeBaseFile {
  name: string;
  path: string;
}

interface KnowledgeBaseItem {
  idx: string;
  name: string;
  active: boolean;
  total: number;
  file_map: Record<string, string>;
}

const emit = defineEmits(["select"]);
const FILE_PREVIEW_COUNT = 5;

const selectedId = ref("");
const knowledgeList = ref<KnowledgeBaseItem[]>([]);
const expandedKnowledgeIds = ref<string[]>([]);
const expandedFileKnowledgeIds = ref<string[]>([]);

const queryKnowledgeBaseList = async () => {
  const data: any = await getKnowledgeBaseList();

  knowledgeList.value = Array.isArray(data) ? data : [data];
  expandedKnowledgeIds.value = knowledgeList.value.map((item) =>
    getKnowledgeId(item),
  );
};

const getKnowledgeId = (knowledge: KnowledgeBaseItem) => {
  return knowledge.idx || knowledge.name;
};

const getKnowledgeFiles = (
  knowledge: KnowledgeBaseItem,
): KnowledgeBaseFile[] => {
  return Object.entries(knowledge.file_map || {}).map(
    ([fileName, filePath]) => ({
      name: fileName,
      path: filePath,
    }),
  );
};

const getFileCount = (knowledge: KnowledgeBaseItem) => {
  return knowledge.total ?? getKnowledgeFiles(knowledge).length;
};

const isExpanded = (knowledgeId: string) => {
  return expandedKnowledgeIds.value.includes(knowledgeId);
};

const getVisibleFiles = (knowledge: KnowledgeBaseItem) => {
  const knowledgeId = knowledge.idx;
  const files = getKnowledgeFiles(knowledge);

  if (isShowingAllFiles(knowledgeId)) {
    return files;
  }

  return files.slice(0, FILE_PREVIEW_COUNT);
};

const isShowingAllFiles = (knowledgeId: string) => {
  return expandedFileKnowledgeIds.value.includes(knowledgeId);
};

const toggleExpand = (knowledgeId: string) => {
  if (isExpanded(knowledgeId)) {
    expandedKnowledgeIds.value = expandedKnowledgeIds.value.filter(
      (id) => id !== knowledgeId,
    );
    return;
  }

  expandedKnowledgeIds.value = [...expandedKnowledgeIds.value, knowledgeId];
};

const toggleMore = (knowledgeId: string) => {
  if (isShowingAllFiles(knowledgeId)) {
    expandedFileKnowledgeIds.value = expandedFileKnowledgeIds.value.filter(
      (id) => id !== knowledgeId,
    );
    return;
  }

  expandedFileKnowledgeIds.value = [
    ...expandedFileKnowledgeIds.value,
    knowledgeId,
  ];
};

const handleCheckChange = async (
  knowledge: KnowledgeBaseItem,
  checked: boolean,
) => {
  const { name } = knowledge;
  await requestKnowledgeBaseUpdate({ name, active: checked });
  queryKnowledgeBaseList();
};

onMounted(() => {
  queryKnowledgeBaseList();
});
</script>

<style scoped lang="less">
.knowledge-menu {
  height: 100%;
  background-color: var(--bg-card-color);
  border-right: 1px solid var(--border-main-color);
}

.menu-wrapper {
  padding: 16px 12px;
  overflow-y: auto;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.menu-header {
  padding: 4px 4px 8px;
}

.menu-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--font-main-color);
  line-height: 1.4;
}

.menu-description {
  margin-top: 6px;
  font-size: var(--font-size-12);
  line-height: 1.5;
  color: var(--font-tip-color);
}

.knowledge-card {
  border: 1px solid var(--border-main-color);
  border-radius: 12px;
  background-color: var(--bg-content-color);
  padding: 14px 12px;
}

.knowledge-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.knowledge-toggle {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.knowledge-title-wrap {
  min-width: 0;
  flex: 1;
}

.knowledge-title {
  font-size: var(--font-size-14);
  font-weight: 600;
  color: var(--font-main-color);
  line-height: 1.4;
  word-break: break-word;
}

.knowledge-count {
  margin-top: 4px;
  font-size: var(--font-size-12);
  color: var(--font-tip-color);
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-left: 16px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background-color: var(--color-primaryBg);
  }

  &.active-file {
    background-color: var(--color-primarySoft);
  }
}

.file-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background-color: var(--color-primary-second);
}

.file-name {
  min-width: 0;
  flex: 1;
  display: inline-block;
  font-size: var(--font-size-13);
  color: var(--font-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toggle-arrow {
  font-size: var(--font-size-12);
  color: var(--color-info);
  transition: transform 0.2s;

  &.open {
    transform: rotate(90deg);
  }
}

.toggle-more {
  margin-top: 10px;
  font-size: var(--font-size-12);
  color: var(--color-primary-hover);
  cursor: pointer;
  user-select: none;
  .flex-end;

  &:hover {
    color: var(--color-primary-hover);
  }
}
</style>
