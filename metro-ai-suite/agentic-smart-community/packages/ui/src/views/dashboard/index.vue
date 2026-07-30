<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
	<div class="app-shell">
		<header class="app-header">
			<h1>Smart Building/Community</h1>
			<div class="header-tools"><span>En</span><button type="button" title="Theme">☼</button></div>
		</header>
		<main class="dashboard">
			<MonitorSidebar :monitors="monitors" :selected-id="selectedId" @select="select" />

			<section class="workspace">
				<header class="toolbar">
					<h2>Video Tracking</h2>
					<div class="toolbar-actions">
						<input v-model="date" type="date" />
						<button class="secondary" type="button" @click="reportOpen = true">▤ {{ t("openReport") }}</button>
					</div>
				</header>

				<template v-if="selectedId">
					<MediaPanel
						v-if="!clipId"
						:monitor-id="selectedId"
						:monitor-name="current?.name || selectedId"
					/>
					<section v-else class="media clip-stage">
						<video :src="smartbuildingApi.clipUrl(clipId, selectedId)" autoplay controls></video>
						<div class="media-copy"><small>{{ current?.name }}</small><strong>Behavior Record</strong></div>
						<span class="mode-pill history-mode">History Replay</span>
						<button class="back-live" type="button" @click="clipId = undefined">↩ Back To Live</button>
					</section>
					<ActivityFeed
						:activities="activities"
						:monitor-id="selectedId"
						:selected-task-id="clipId"
						@clip="clipId = $event"
					/>
				</template>
				<div v-else class="workspace-empty">{{ loading ? t("loading") : t("noMonitors") }}</div>
			</section>

			<aside class="right-rail">
				<ChatPanel :configured="config?.chat === 'configured'" />
			</aside>

			<button class="token-trigger" type="button" :title="t('tokens')" @click="tokenOpen = !tokenOpen">▥</button>
			<div v-if="tokenOpen" class="token-popover">
				<RouterStatsCard :status="router" :local-total="stats.totalTokens" @refresh="refreshTokenStats" @close="tokenOpen = false" />
			</div>

			<ReportDrawer
				v-if="reportOpen"
				:reports="reports"
				:generating="generating"
				@close="reportOpen = false"
				@generate="selectedId && generate(selectedId, date)"
			/>
		</main>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { smartbuildingApi } from "../../api/smartbuilding.js";
import { useMonitors } from "../../composables/useMonitors.js";
import { useActivities } from "../../composables/useActivities.js";
import { useReports } from "../../composables/useReports.js";
import { useIntegrationStatus } from "../../composables/useIntegrationStatus.js";
import MonitorSidebar from "./components/MonitorSidebar.vue";
import MediaPanel from "./components/MediaPanel.vue";
import ActivityFeed from "./components/ActivityFeed.vue";
import RouterStatsCard from "./components/RouterStatsCard.vue";
import ChatPanel from "./components/ChatPanel.vue";
import ReportDrawer from "./components/ReportDrawer.vue";

const { t } = useI18n();
const route = useRoute();
const routerApi = useRouter();
const { monitors, loading, refresh } = useMonitors();
const { activities, load: loadActivities } = useActivities();
const { reports, generating, load: loadReports, generate } = useReports();
const { config, router, load: loadIntegrations } = useIntegrationStatus();
const selectedId = ref("");
const date = ref(new Date().toISOString().slice(0, 10));
const reportOpen = ref(false);
const tokenOpen = ref(false);
const clipId = ref<number>();
const stats = reactive({ totalTokens: 0, activities: 0, alerts: 0 });
const current = computed(() => monitors.value.find((item) => item.id === selectedId.value));

const select = (id: string) => {
	selectedId.value = id;
	clipId.value = undefined;
	void routerApi.replace({ query: { ...route.query, monitor_id: id } });
};

const loadSelection = async () => {
	if (!selectedId.value) return;
	await Promise.all([
		loadActivities(selectedId.value, date.value),
		loadReports(selectedId.value, date.value),
		smartbuildingApi.stats(selectedId.value, date.value).then((value) => Object.assign(stats, value)),
	]);
};

const refreshTokenStats = async () => {
	await Promise.all([loadIntegrations(), loadSelection()]);
};

watch([selectedId, date], () => { void loadSelection(); });
onMounted(async () => {
	await Promise.all([refresh(), loadIntegrations()]);
	const requested = typeof route.query.monitor_id === "string" ? route.query.monitor_id : "";
	select(monitors.value.some((item) => item.id === requested) ? requested : monitors.value.find((item) => item.status === "online")?.id || monitors.value[0]?.id || "");
});
</script>