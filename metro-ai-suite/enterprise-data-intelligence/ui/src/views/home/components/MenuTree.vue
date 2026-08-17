<!--
  Copyright (C) 2026 Intel Corporation
  SPDX-License-Identifier: Apache-2.0
-->

<template>
  <div class="menu-tree">
    <div v-for="node in nodes" :key="node.idx" class="tree-node">
      <div
        class="node-item"
        :class="{
          'active-node': selectedId === node.idx,
          ' ancestor-node': isAncestor(node.idx),
        }"
        @click="handleSelect(node)"
      >
        <div class="left-wrap">
          <SvgIcon
            v-if="isFolder(node)"
            :name="isOpen(node.idx) ? 'icon-folder-open' : 'icon-folder-close'"
            :size="18"
            :style="{ color: 'var(--color-primary)' }"
          />

          <FileTextOutlined
            v-else
            :style="{ color: 'var(--color-info)', fontSize: '18px' }"
          />
          <span class="node-name">{{ node.name }}</span>
        </div>
        <div
          v-if="isFolder(node)"
          class="arrow-wrap"
          @click.stop="toggleExpand(node.idx)"
        >
          <RightOutlined :class="{ open: isOpen(node.idx) }" />
        </div>
      </div>

      <div v-if="isFolder(node) && isOpen(node.idx)" class="child-tree">
        <MenuTree
          :nodes="node.children!"
          :selectedId="selectedId"
          :openKeys="openKeys"
          :parentPath="[
            ...(parentPath || []),
            { id: node.idx, name: node.name },
          ]"
          :selectedPathIds="selectedPathIds"
          @update:openKeys="emitOpen"
          @select="emitSelect"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts" name="MenuTree">
import { computed } from "vue";
import SvgIcon from "@/components/SvgIcon.vue";
import { RightOutlined, FileTextOutlined } from "@ant-design/icons-vue";

interface TreeNode {
  idx: string;
  name: string;
  children?: TreeNode[];
}

const props = defineProps<{
  nodes: TreeNode[];
  selectedId: string;
  openKeys: string[];
  parentPath?: { id: string; name: string }[];
  selectedPathIds?: string[];
}>();

const emit = defineEmits(["update:openKeys", "select"]);

const selectedId = computed(() => props.selectedId);

const isFolder = (node: TreeNode) => !!node.children?.length;

const isOpen = (id: string) => props.openKeys.includes(id);

const isAncestor = (id: string) => {
  return props.selectedPathIds?.includes(id) && id !== props.selectedId;
};

const toggleExpand = (id: string) => {
  const arr = [...props.openKeys];
  const idx = arr.indexOf(id);

  if (idx > -1) arr.splice(idx, 1);
  else arr.push(id);

  emit("update:openKeys", arr);
};

const buildPath = (node: TreeNode) => {
  const parent = props.parentPath || [];
  const fullPath = [...parent, { id: node.idx, name: node.name }];

  return {
    pathArray: fullPath.map((i) => i.name),
    pathIds: fullPath.map((i) => i.id),
  };
};

const handleSelect = (node: TreeNode) => {
  const { pathArray, pathIds } = buildPath(node);

  emit("select", {
    id: node.idx,
    pathArray,
    pathIds,
  });

  if (isFolder(node)) toggleExpand(node.idx);
};

const emitSelect = (payload: any) => emit("select", payload);
const emitOpen = (keys: string[]) => emit("update:openKeys", keys);
</script>

<style scoped lang="less">
.menu-tree {
  .flex-column;
  gap: 2px;
  .tree-node {
    .flex-column;
    .node-item {
      .flex-between;
      position: relative;
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
      user-select: none;
      border-bottom: 4px solid transparent;

      &:hover {
        background: var(--color-primaryBg);
      }

      &.ancestor-node {
        background: var(--color-primarySoft);
      }

      &.active-node {
        background: var(--color-primaryBg);

        .node-name {
          color: var(--color-primary-hover);
          font-weight: 500;
          &::before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: var(--color-primary-hover);
          }
        }
      }
    }
    .left-wrap {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .child-tree {
      padding-left: 24px;
    }

    .node-icon {
      width: 16px;
      height: 16px;
      flex-shrink: 0;
    }

    .node-name {
      font-size: var(--font-size-14);
      color: #333;
    }

    .arrow-wrap {
      font-size: var(--font-size-12);
      color: var(--color-info);
      display: flex;

      .open {
        transform: rotate(90deg);
      }
    }
  }
}
</style>
