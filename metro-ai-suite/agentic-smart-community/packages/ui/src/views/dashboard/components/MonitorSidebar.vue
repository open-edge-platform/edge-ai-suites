<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
	<aside class="sidebar">
		<div class="section-label">Device List</div>
		<div v-if="!monitors.length" class="empty">{{ t("noMonitors") }}</div>
		<div class="monitor-list">
			<button v-for="monitor in onlineMonitors" :key="monitor.id" class="monitor" :class="{ active: monitor.id === selectedId }" @click="$emit('select', monitor.id)">
				<span class="monitor-indicator"></span>
				<span class="monitor-copy"><strong>{{ monitor.name }}</strong><small>{{ locationLabel(monitor) }}</small></span>
				<span class="state online"><i></i>{{ t("online") }}</span>
			</button>
		</div>
		<div v-if="offlineMonitors.length" class="offline-group">
			<button class="offline-toggle" type="button" :aria-expanded="offlineOpen" @click="offlineOpen = !offlineOpen">
				<span>{{ t("offlineMonitors") }} ({{ offlineMonitors.length }})</span><span :class="{ open: offlineOpen }">⌄</span>
			</button>
			<div v-if="offlineOpen" class="monitor-list offline-list">
				<button v-for="monitor in offlineMonitors" :key="monitor.id" class="monitor" :class="{ active: monitor.id === selectedId }" @click="$emit('select', monitor.id)">
					<span class="monitor-indicator"></span>
					<span class="monitor-copy"><strong>{{ monitor.name }}</strong><small>{{ locationLabel(monitor) }}</small></span>
					<span class="state" :class="monitor.status"><i></i>{{ t(monitor.status) }}</span>
				</button>
			</div>
		</div>
	</aside>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { SmartbuildingMonitor } from "../../../types/smartbuilding.js";

const props = defineProps<{ monitors: SmartbuildingMonitor[]; selectedId: string }>();
defineEmits<{ select: [id: string] }>();
const { t } = useI18n();
const offlineOpen = ref(false);
const onlineMonitors = computed(() => props.monitors.filter((monitor) => monitor.status === "online"));
const offlineMonitors = computed(() => props.monitors.filter((monitor) => monitor.status !== "online"));
const locationLabel = (monitor: SmartbuildingMonitor) => monitor.useCase.replaceAll("_", " ");
</script>