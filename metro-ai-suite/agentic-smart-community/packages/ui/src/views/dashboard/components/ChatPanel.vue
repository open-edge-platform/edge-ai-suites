<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
	<section class="chat">
		<header><h2>{{ t("chat") }}</h2><span class="availability" :class="{ on: connected }"></span></header>
		<div v-if="!configured" class="chat-empty">
			<strong>{{ t("chatUnconfigured") }}</strong>
			<p>Dashboard monitoring remains available.</p>
		</div>
		<template v-else>
			<div class="chat-messages">
				<p v-for="message in messages" :key="message.id" :class="message.role">{{ message.text }}</p>
			</div>
			<form class="chat-form" @submit.prevent="send">
				<input v-model="question" :disabled="!sessionKey" placeholder="Message OpenClaw" maxlength="4000" />
				<button type="submit" :disabled="!question.trim() || !sessionKey" aria-label="Send">↑</button>
			</form>
		</template>
	</section>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

const props = defineProps<{ configured: boolean }>();
const { t } = useI18n();
const connected = ref(false);
const question = ref("");
const sessionKey = ref("");
const messages = ref<Array<{ id: string; role: "user" | "assistant"; text: string }>>([]);
let socket: WebSocket | undefined;
let sequence = 0;
const pending = new Map<string, (payload: Record<string, unknown>) => void>();

function request(method: string, params: Record<string, unknown>): Promise<Record<string, unknown>> {
	if (!socket || socket.readyState !== WebSocket.OPEN) return Promise.reject(new Error("Chat unavailable"));
	const id = `ui-${Date.now()}-${sequence++}`;
	socket.send(JSON.stringify({ type: "req", id, method, params }));
	return new Promise((resolve) => pending.set(id, resolve));
}

async function initialize(): Promise<void> {
	await request("connect", {
		minProtocol: 3,
		maxProtocol: 3,
		client: { id: "smartbuilding-dashboard", version: "0.1.0", platform: navigator.platform, mode: "webchat" },
		role: "operator",
		scopes: ["operator.read", "operator.write"],
		caps: [],
		locale: navigator.language,
	});
	const catalog = await request("sessions.list", { includeGlobal: true, includeUnknown: false });
	const sessions = Array.isArray(catalog.sessions) ? catalog.sessions as Array<{ key?: string }> : [];
	sessionKey.value = sessions.find((item) => item.key)?.key ?? "";
	if (!sessionKey.value) return;
	const history = await request("chat.history", { sessionKey: sessionKey.value, limit: 50 });
	const rows = Array.isArray(history.messages) ? history.messages as Array<Record<string, unknown>> : [];
	messages.value = rows.map((row, index) => ({
		id: `history-${index}`,
		role: row.role === "user" ? "user" : "assistant",
		text: String(row.content ?? row.text ?? ""),
	}));
}

function connect(): void {
	disconnect();
	if (!props.configured) return;
	const protocol = location.protocol === "https:" ? "wss:" : "ws:";
	const nextSocket = new WebSocket(`${protocol}//${location.host}/api/chat`);
	socket = nextSocket;
	nextSocket.onopen = () => {
		if (socket !== nextSocket) return;
		connected.value = true;
		void initialize().catch(disconnect);
	};
	nextSocket.onmessage = (event) => {
		if (socket !== nextSocket) return;
		const frame = JSON.parse(String(event.data)) as Record<string, any>;
		if (frame.type === "res" && frame.id && pending.has(frame.id)) {
			const resolve = pending.get(frame.id)!;
			pending.delete(frame.id);
			resolve(frame.payload ?? {});
		} else if (frame.type === "event" && frame.event === "chat") {
			const payload = frame.payload ?? {};
			const text = String(payload.data?.text ?? payload.text ?? "").trim();
			if (text) messages.value.push({ id: `event-${Date.now()}-${sequence++}`, role: "assistant", text });
		}
	};
	nextSocket.onclose = () => {
		if (socket !== nextSocket) return;
		connected.value = false;
		pending.clear();
	};
	nextSocket.onerror = disconnect;
}

function disconnect(): void {
	const previous = socket;
	socket = undefined;
	previous?.close();
	if (previous) {
		previous.onopen = null;
		previous.onmessage = null;
		previous.onclose = null;
		previous.onerror = null;
	}
	connected.value = false;
	sessionKey.value = "";
	pending.clear();
}

function send(): void {
	const text = question.value.trim();
	if (!text || !sessionKey.value) return;
	question.value = "";
	messages.value.push({ id: `user-${Date.now()}`, role: "user", text });
	void request("chat.send", {
		sessionKey: sessionKey.value,
		message: text,
		deliver: false,
		idempotencyKey: crypto.randomUUID(),
	});
}

watch(() => props.configured, connect, { immediate: true });
onBeforeUnmount(disconnect);
</script>

<style scoped>
.chat { display: flex; flex-direction: column; }
.chat-messages { flex: 1; overflow: auto; padding: 12px 0; }
.chat-messages p { max-width: 88%; padding: 9px 10px; margin: 6px 0; background: #edf1ee; border-radius: 6px; font-size: 13px; white-space: pre-wrap; }
.chat-messages p.user { margin-left: auto; background: #dcebdc; }
.chat-form { display: grid; grid-template-columns: 1fr 36px; gap: 6px; }
.chat-form input { min-width: 0; height: 38px; border: 1px solid var(--line); padding: 0 10px; }
.chat-form button { border: 0; background: var(--ink); color: white; border-radius: 4px; }
</style>