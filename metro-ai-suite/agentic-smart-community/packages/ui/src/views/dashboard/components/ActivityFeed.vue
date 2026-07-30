<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
	<section class="timeline-card">
		<header class="timeline-header">
			<h3>Today's Activity Timeline</h3>
			<div class="event-filters">
				<button
					v-for="type in eventTypes"
					:key="type"
					type="button"
					:class="['filter-chip', tone(type), { active: selectedTypes.includes(type) }]"
					@click="toggleType(type)"
				><span></span>{{ label(type) }}</button>
				<small>Wheel to zoom, drag to browse time</small>
			</div>
		</header>
		<div
			v-if="filteredActivities.length"
			ref="timelineScroll"
			class="timeline-scroll"
			:class="{ dragging }"
			@wheel.prevent="zoomTimeline"
			@mousedown="startDrag"
			@mousemove="dragTimeline"
			@mouseup="stopDrag"
			@mouseleave="stopDrag"
		>
			<div class="timeline-canvas" :style="{ width: `${timelineScale * 100}%` }">
				<div class="timeline-track">
					<button
						v-for="item in filteredActivities"
						:key="item.task.id"
						type="button"
						:class="['timeline-mark', tone(eventType(item)), { active: item.task.id === selectedTaskId }]"
						:style="{ left: `${position(item)}%` }"
						:title="`${formatTime(item.task.createdAt)} ${label(eventType(item))}`"
						@click="selectItem(item)"
					></button>
				</div>
				<div class="timeline-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
			</div>
		</div>
		<div v-else class="timeline-empty">{{ t("noActivity") }}</div>
	</section>

	<section class="activity-records">
		<h3>Activity Records</h3>
		<div v-if="!filteredActivities.length" class="empty">{{ t("noActivity") }}</div>
		<div v-else class="record-list">
			<article
				v-for="item in filteredActivities"
				:id="`activity-${item.task.id}`"
				:key="item.task.id"
				:class="['record-item', { active: item.task.id === selectedTaskId }]"
			>
				<div class="record-time"><strong>{{ formatTime(item.task.createdAt) }}</strong><small>{{ formatDate(item.task.createdAt) }}</small></div>
				<span class="record-node"></span>
				<button class="summary-card" type="button" @click="selectItem(item)">
					<div class="summary-head">
						<strong>Behavior Record</strong>
						<div class="summary-badges">
							<span class="complete">● {{ item.task.status }}</span>
							<span :class="tone(eventType(item))">{{ label(eventType(item)) }}</span>
							<span v-if="item.task.clipDuration" class="duration">Duration {{ Number(item.task.clipDuration).toFixed(1) }} sec</span>
						</div>
					</div>
					<p>{{ summary(item) }}</p>
					<div v-if="item.task.summaryClipInput" class="clip-preview">
						<video :src="smartbuildingApi.clipUrl(item.task.id, monitorId)" preload="metadata" muted></video>
						<span class="play-button">▶</span>
					</div>
				</button>
			</article>
		</div>
	</section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { smartbuildingApi } from "../../../api/smartbuilding.js";
import type { SmartbuildingActivity } from "../../../types/smartbuilding.js";

const props = defineProps<{ activities: SmartbuildingActivity[]; monitorId: string; selectedTaskId?: number }>();
const emit = defineEmits<{ clip: [taskId: number] }>();
const { t } = useI18n();
const selectedTypes = ref<string[]>([]);
const filtersInitialized = ref(false);
const timelineScroll = ref<HTMLElement>();
const timelineScale = ref(1);
const dragging = ref(false);
const dragStartX = ref(0);
const dragStartScroll = ref(0);

const eventType = (item: SmartbuildingActivity) => String(item.task.event ?? item.task.alert_type ?? item.event?.motionType ?? (item.alert ? "danger" : "normal"));
const eventTypes = computed(() => [...new Set(props.activities.map(eventType))]);
const filteredActivities = computed(() => props.activities.filter((item) => selectedTypes.value.includes(eventType(item))));
const label = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const tone = (value: string) => /danger|critical|warn|fall|fire|knife|climb/i.test(value) ? "danger" : "normal";
const formatTime = (value: string) => value.includes("T") ? value.slice(11, 19) : value.slice(11, 19);
const formatDate = (value: string) => value.slice(0, 10);
const position = (item: SmartbuildingActivity) => {
	const [hours = 0, minutes = 0, seconds = 0] = formatTime(item.task.createdAt).split(":").map(Number);
	return Math.min(99.2, Math.max(0.8, ((hours * 3600 + minutes * 60 + seconds) / 86400) * 100));
};
const summary = (item: SmartbuildingActivity) => item.task.summaryText || item.alert?.description || item.event?.motionType || "Video summary task";
const toggleType = (type: string) => { selectedTypes.value = selectedTypes.value.includes(type) ? selectedTypes.value.filter((value) => value !== type) : [...selectedTypes.value, type]; };
const zoomTimeline = (event: WheelEvent) => {
	const element = timelineScroll.value;
	if (!element) return;
	const previousScale = timelineScale.value;
	const nextScale = Math.min(8, Math.max(1, previousScale * (event.deltaY < 0 ? 1.35 : .74)));
	const pointer = event.clientX - element.getBoundingClientRect().left;
	const logicalPosition = (element.scrollLeft + pointer) / previousScale;
	timelineScale.value = nextScale;
	void nextTick(() => { element.scrollLeft = logicalPosition * nextScale - pointer; });
};
const startDrag = (event: MouseEvent) => {
	if ((event.target as HTMLElement).closest("button")) return;
	dragging.value = true;
	dragStartX.value = event.clientX;
	dragStartScroll.value = timelineScroll.value?.scrollLeft ?? 0;
};
const dragTimeline = (event: MouseEvent) => {
	if (!dragging.value || !timelineScroll.value) return;
	timelineScroll.value.scrollLeft = dragStartScroll.value - (event.clientX - dragStartX.value);
};
const stopDrag = () => { dragging.value = false; };
const selectItem = (item: SmartbuildingActivity) => {
	if (item.task.summaryClipInput) emit("clip", item.task.id);
	void nextTick(() => document.getElementById(`activity-${item.task.id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
};
watch(eventTypes, (types) => {
	if (!filtersInitialized.value && types.length) {
		selectedTypes.value = [...types];
		filtersInitialized.value = true;
		return;
	}
	selectedTypes.value = selectedTypes.value.filter((type) => types.includes(type));
});
</script>