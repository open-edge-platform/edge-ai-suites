<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template><section class="media"><video ref="video" autoplay muted playsinline controls></video><img v-if="fallback" :src="snapshot" alt="Latest monitor snapshot" /><div class="media-copy"><small>{{ monitorName }}</small><strong>Live Monitoring</strong></div><div class="live-badge"><span></span>{{ t('live') }}</div><div v-if="fallback" class="fallback">{{ t('liveUnavailable') }}</div></section></template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { smartbuildingApi } from "../../../api/smartbuilding.js";

const MAX_QUEUE_BYTES = 8 * 1024 * 1024;
const MAX_BUFFER_SECONDS = 30;
const RETAIN_BUFFER_SECONDS = 20;

const props = defineProps<{ monitorId: string; monitorName: string }>();
const { t } = useI18n();
const video = ref<HTMLVideoElement>();
const fallback = ref(false);
const snapshotTick = ref(Date.now());
const snapshot = computed(() => `${smartbuildingApi.snapshotUrl(props.monitorId)}&tick=${snapshotTick.value}`);

let cleanupStream: (() => void) | undefined;
let snapshotTimer: number | undefined;

function stopSnapshotRefresh(): void {
	if (snapshotTimer !== undefined) window.clearInterval(snapshotTimer);
	snapshotTimer = undefined;
}

function showSnapshotFallback(): void {
	fallback.value = true;
	stopSnapshotRefresh();
	snapshotTick.value = Date.now();
	snapshotTimer = window.setInterval(() => { snapshotTick.value = Date.now(); }, 2_000);
}

function startStream(): void {
	cleanupStream?.();
	stopSnapshotRefresh();
	fallback.value = false;
	if (!props.monitorId || !video.value || !("MediaSource" in window)) {
		showSnapshotFallback();
		return;
	}

	const controller = new AbortController();
	const mediaSource = new MediaSource();
	const objectUrl = URL.createObjectURL(mediaSource);
	const queue: ArrayBuffer[] = [];
	let queuedBytes = 0;
	let sourceBuffer: SourceBuffer | undefined;
	let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
	let disposed = false;

	const pump = () => {
		if (!sourceBuffer || sourceBuffer.updating || disposed) return;
		if (sourceBuffer.buffered.length) {
			const start = sourceBuffer.buffered.start(0);
			const end = sourceBuffer.buffered.end(sourceBuffer.buffered.length - 1);
			if (end - start > MAX_BUFFER_SECONDS) {
				sourceBuffer.remove(start, end - RETAIN_BUFFER_SECONDS);
				return;
			}
		}
		const chunk = queue.shift();
		if (!chunk) return;
		queuedBytes -= chunk.byteLength;
		sourceBuffer.appendBuffer(chunk);
	};

	const onSourceOpen = async () => {
		try {
			if (disposed) return;
			sourceBuffer = mediaSource.addSourceBuffer('video/mp4; codecs="avc1.42E01E"');
			sourceBuffer.addEventListener("updateend", pump);
			const response = await fetch(smartbuildingApi.liveUrl(props.monitorId), { signal: controller.signal });
			if (!response.ok || !response.body) throw new Error("stream unavailable");
			reader = response.body.getReader();
			while (!disposed) {
				const { done, value } = await reader.read();
				if (done) break;
				if (queuedBytes + value.byteLength > MAX_QUEUE_BYTES) throw new Error("stream buffer exceeded");
				const chunk = value.slice().buffer as ArrayBuffer;
				queue.push(chunk);
				queuedBytes += chunk.byteLength;
				pump();
			}
		} catch (error) {
			if (!disposed && !(error instanceof DOMException && error.name === "AbortError")) {
				cleanupStream?.();
				showSnapshotFallback();
			}
		}
	};

	cleanupStream = () => {
		if (disposed) return;
		disposed = true;
		controller.abort();
		void reader?.cancel().catch(() => undefined);
		mediaSource.removeEventListener("sourceopen", onSourceOpen);
		sourceBuffer?.removeEventListener("updateend", pump);
		queue.length = 0;
		queuedBytes = 0;
		if (mediaSource.readyState === "open") {
			try { mediaSource.endOfStream(); } catch { /* Stream may already be closing. */ }
		}
		if (video.value) {
			video.value.pause();
			video.value.removeAttribute("src");
			video.value.load();
		}
		URL.revokeObjectURL(objectUrl);
	};

	video.value.src = objectUrl;
	mediaSource.addEventListener("sourceopen", onSourceOpen, { once: true });
}

const onVisibilityChange = () => {
	if (document.hidden) {
		cleanupStream?.();
		stopSnapshotRefresh();
	} else if (fallback.value) {
		showSnapshotFallback();
	} else {
		startStream();
	}
};

document.addEventListener("visibilitychange", onVisibilityChange);
watch(() => props.monitorId, startStream, { immediate: true, flush: "post" });
onBeforeUnmount(() => {
	document.removeEventListener("visibilitychange", onVisibilityChange);
	cleanupStream?.();
	stopSnapshotRefresh();
});
</script>