<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
	<section class="stat-card">
		<header><h2>{{ t("tokens") }}</h2><div><button class="icon-button" :title="t('refresh')" @click="$emit('refresh')">↻</button><button class="icon-button" :title="t('close')" @click="$emit('close')">×</button></div></header>
		<div class="token-split"><div><small>Local</small><strong>{{ compact(localTotal) }}</strong></div><div><small>Cloud</small><strong>{{ cloudTotal }}</strong></div></div>
		<div class="token-ring"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="44"/><circle class="progress" cx="60" cy="60" r="44" :style="{ strokeDasharray: `${localShare * 2.764} 276.4` }"/></svg><div><strong>{{ localShare.toFixed(1) }}%</strong><small>Local</small></div></div>
		<div class="token-total"><span>Total Tokens</span><strong>{{ compact(localTotal) }}</strong></div>
		<div v-if="status.status === 'not_configured'" class="integration-empty">{{ t("routerUnconfigured") }}</div>
		<div v-else-if="status.status === 'unavailable'" class="integration-empty warning">{{ t("routerUnavailable") }}</div>
	</section>
</template>
<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { RouterStats } from "../../../types/smartbuilding.js";
const props = defineProps<{ status: RouterStats; localTotal: number }>();
defineEmits<{ refresh: []; close: [] }>();
const { t } = useI18n();
const cloudValue = computed(() => Number((props.status.data as any)?.token_metrics?.cloud_model?.total_tokens ?? 0));
const cloudTotal = computed(() => compact(cloudValue.value));
const localShare = computed(() => props.localTotal + cloudValue.value > 0 ? props.localTotal / (props.localTotal + cloudValue.value) * 100 : 0);
const compact = (value: number) => new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
</script>