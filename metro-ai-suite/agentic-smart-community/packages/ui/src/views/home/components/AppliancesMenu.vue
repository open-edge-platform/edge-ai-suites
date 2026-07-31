<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<template>
  <div class="appliance-menu">
    <div class="menu-wrapper flex-column">
      <template v-if="applianceList.length">
        <div class="menu-section flex-column">
          <div class="section-kicker">
            {{ $t("smartHome.cameraSectionLabel") }}
          </div>

          <div
            v-if="onlineAppliances.length"
            class="appliance-tabs flex-column"
            role="tablist"
          >
            <div
              v-for="appliance in onlineAppliances"
              :key="appliance.id"
              class="appliance-item"
            >
              <div
                class="appliance-tab"
                :class="{ active: appliance.id === expandedAppliance?.id }"
              >
                <button
                  type="button"
                  class="appliance-tab-trigger"
                  @click="handleSelectAppliance(appliance.id)"
                >
                  <span class="appliance-tab-indicator"></span>

                  <span class="appliance-tab-body flex-column">
                    <span class="appliance-tab-topline flex-left">
                      <span class="appliance-tab-name">{{
                        appliance.name
                      }}</span>
                    </span>
                    <span class="appliance-tab-meta">
                      {{ appliance.location }}
                    </span>
                  </span>

                  <span class="appliance-tab-aside flex-left">
                    <span class="appliance-tab-status vertical-center">
                      <span class="status-dot"></span
                      >{{ appliance.status }}</span
                    >
                  </span>
                </button>
              </div>
            </div>
          </div>

          <div v-if="offlineAppliances.length" class="offline-appliances">
            <button
              class="offline-toggle"
              type="button"
              :aria-expanded="showOfflineAppliances"
              @click="showOfflineAppliances = !showOfflineAppliances"
            >
              <span>{{ $t("smartHome.offlineCameras") }} ({{ offlineAppliances.length }})</span>
              <DownOutlined :class="{ open: showOfflineAppliances }" />
            </button>
            <div v-if="showOfflineAppliances" class="appliance-tabs flex-column">
              <div
                v-for="appliance in offlineAppliances"
                :key="appliance.id"
                class="appliance-item offline"
              >
                <div
                  class="appliance-tab"
                  :class="{ active: appliance.id === expandedAppliance?.id }"
                >
                  <button
                    type="button"
                    class="appliance-tab-trigger"
                    @click="handleSelectAppliance(appliance.id)"
                  >
                    <span class="appliance-tab-indicator"></span>
                    <span class="appliance-tab-body flex-column">
                      <span class="appliance-tab-name">{{ appliance.name }}</span>
                      <span class="appliance-tab-meta">{{ appliance.location }}</span>
                    </span>
                    <span class="appliance-tab-status vertical-center">
                      <span class="status-dot"></span>{{ appliance.status }}
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <div v-else class="menu-empty-state vertical-center">
        <a-empty :description="$t('smartHome.noCameraData')" />
      </div>

      <div class="menu-monitor-pane" :class="{ open: isMonitorOpen }">
        <button
          v-if="!isMonitorOpen"
          class="monitor-trigger"
          type="button"
          :title="t('monitor.title')"
          @click="openMonitor"
        >
          <span class="monitor-trigger-icon vertical-center">
            <BarChartOutlined />
          </span>
        </button>

        <div class="monitor-pane" :class="{ open: isMonitorOpen }">
          <TokenSaving
            :selected-date="selectedDateLabel"
            :selected-source-id="selectedSourceId"
            embedded
            embedded-closable
            @close="closeMonitor"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Dayjs } from "dayjs";
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { BarChartOutlined, DownOutlined } from "@ant-design/icons-vue";
import { getMonitors } from "@/api/smartHome";
import TokenSaving from "@/components/TokenSaving.vue";
import { getSmartHomeSourceMeta } from "../deviceMeta";

const props = defineProps<{
  selectedDate: Dayjs;
}>();

interface ApplianceInfo {
  id: string;
  name: string;
  location?: string;
  status?: string;
  [key: string]: unknown;
}

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const monitors = ref<ApplianceInfo[]>([]);
const isMonitorOpen = ref(false);
const showOfflineAppliances = ref(false);
let monitorPollingTimer: number | null = null;

const openMonitor = () => {
  isMonitorOpen.value = true;
};

const closeMonitor = () => {
  isMonitorOpen.value = false;
};

const getAppliancePreset = (sourceId: string): Partial<ApplianceInfo> => {
  const meta = getSmartHomeSourceMeta(sourceId, t);

  return {
    location: meta.location,
    status: t("smartHome.deviceOnline"),
  };
};

const formatLocation = (value: unknown) => {
  return typeof value === "string" && value.trim()
    ? value.trim()
    : t("smartHome.applianceLocationFallback");
};

const formatName = (monitor: ApplianceInfo) => {
  const monitorName =
    typeof monitor.name === "string" ? monitor.name.trim() : "";
  if (monitorName) {
    return monitorName;
  }

  const preset = getAppliancePreset(monitor.id);
  return preset?.name || `${t("smartHome.applianceGenericName")} ${monitor.id}`;
};

const buildApplianceInfo = (monitor: ApplianceInfo): ApplianceInfo => {
  const preset = getAppliancePreset(monitor.id);
  const location = formatLocation(monitor.location ?? preset?.location);

  return {
    ...preset,
    ...monitor,
    name: formatName(monitor),
    location,
    status: monitor.status || preset?.status || t("smartHome.deviceOnline"),
  };
};

const applianceList = computed(() => monitors.value.map(buildApplianceInfo));
const onlineAppliances = computed(() =>
  applianceList.value.filter((monitor) => monitor.status === "online"),
);
const offlineAppliances = computed(() =>
  applianceList.value.filter((monitor) => monitor.status !== "online"),
);

const selectedSourceId = computed(() => {
  const sourceId = route.query.source_id;
  return typeof sourceId === "string" ? sourceId : "";
});

const selectedDateLabel = computed(() => {
  return props.selectedDate.format("YYYY-MM-DD");
});

const expandedAppliance = computed(() => {
  if (!selectedSourceId.value) {
    return null;
  }

  return (
    applianceList.value.find((item) => item.id === selectedSourceId.value) ??
    null
  );
});

const updateSelection = async (appliance: ApplianceInfo) => {
  await router.replace({
    query: {
      ...route.query,
      source_id: appliance.id,
    },
  });
};

const handleSelectAppliance = (applianceId: string) => {
  const appliance = applianceList.value.find((item) => item.id === applianceId);
  if (!appliance) {
    return;
  }

  void updateSelection(appliance);
};

const queryMonitors = async () => {
  try {
    const response = await getMonitors({});
    monitors.value = response?.monitors || [];

    const matchedMonitor = monitors.value.find(
      (monitor) => monitor.id === selectedSourceId.value,
    );

    if (matchedMonitor) {
      return;
    }

    const firstOnlineMonitor = monitors.value.find(
      (monitor) => monitor.status === "online",
    );
    if (!matchedMonitor && (firstOnlineMonitor || monitors.value[0])) {
      await updateSelection(firstOnlineMonitor || monitors.value[0]);
    }
  } catch {
    monitors.value = [];
  }
};

onMounted(() => {
  void queryMonitors();
  monitorPollingTimer = window.setInterval(queryMonitors, 30 * 1000);
});

onUnmounted(() => {
  if (monitorPollingTimer !== null) {
    window.clearInterval(monitorPollingTimer);
  }
});
</script>

<style scoped lang="less">
.appliance-menu {
  height: 100%;
  background: var(--surface-panel-bg);
  border: 1px solid var(--border-primary);
  border-radius: 24px;
  overflow: hidden;
}

.menu-wrapper {
  height: 100%;
  overflow-y: auto;
  padding: 16px;
  gap: 16px;
}

.menu-monitor-pane {
  position: sticky;
  bottom: 0;
  z-index: 2;
  margin-top: auto;
  min-height: 0;
  isolation: isolate;
}

.menu-monitor-pane.open {
  padding: 14px 10px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--surface-panel-bg) 0%, transparent) 0%,
    color-mix(in srgb, var(--surface-card-bg) 42%, var(--surface-panel-bg) 58%)
      20%,
    var(--surface-panel-bg) 100%
  );
  border-radius: 18px 18px 0 0;
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--border-primary) 68%, transparent),
    0 -10px 22px color-mix(in srgb, var(--bg-box-shadow) 18%, transparent);
}

.menu-monitor-pane.open::before {
  content: "";
  position: absolute;
  top: 0;
  left: 12px;
  right: 12px;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent 0%,
    color-mix(in srgb, var(--border-primary) 82%, transparent) 18%,
    color-mix(in srgb, var(--border-primary) 82%, transparent) 82%,
    transparent 100%
  );
  pointer-events: none;
}

.menu-header {
  padding: 4px 2px 2px;
}

.menu-title {
  font-size: var(--font-size-16);
  font-weight: 700;
  color: var(--font-main-color);
}

.menu-subtitle {
  font-size: var(--font-size-13);
  line-height: 1.6;
  color: var(--font-tip-color);
}

.menu-section {
  gap: 10px;
}

.section-kicker {
  padding: 0 4px;
  font-size: var(--font-size-11);
  font-weight: 700;
  letter-spacing: 1.1px;
  text-transform: uppercase;
  color: var(--font-tip-color);
}

.appliance-tabs {
  gap: 8px;
}

.offline-appliances {
  padding-top: 2px;
}

.offline-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px;
  border: 0;
  background: transparent;
  color: var(--font-tip-color);
  cursor: pointer;
}

.offline-toggle :deep(.intelicon) {
  transition: transform 0.2s ease;
}

.offline-toggle :deep(.open) {
  transform: rotate(180deg);
}

.appliance-item.offline {
  .appliance-tab-body {
    opacity: 0.68;
  }

  .appliance-tab-status {
    color: var(--font-text-color);
    background: color-mix(in srgb, var(--font-text-color) 14%, transparent);

    .status-dot {
      background: var(--font-text-color);
    }
  }
}

.appliance-item {
  display: block;
}

.appliance-tab {
  border-radius: 14px;
  border: 1px solid var(--border-primary);
  width: 100%;
  background: var(--surface-card-bg);
  color: var(--font-main-color);
  overflow: hidden;
}

.appliance-tab-trigger {
  width: 100%;
  cursor: pointer;
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 11px 12px 11px 10px;
  text-align: left;
  border: 0;
  background: transparent;
  color: inherit;
}

.appliance-tab:hover,
.appliance-tab.active {
  transform: translateY(-1px);
  border-color: var(--color-primary);
  box-shadow: 0 8px 18px var(--bg-box-shadow);
}

.appliance-tab.active {
  background: var(--surface-card-bg-hover);
}

.appliance-tab-indicator {
  width: 4px;
  height: 100%;
  min-height: 28px;
  border-radius: 999px;
  background: var(--border-primary);
  transition: background 0.2s ease;
}

.appliance-tab.active .appliance-tab-indicator {
  background: var(--color-primary);
}

.appliance-tab-body {
  min-width: 0;
  gap: 2px;
}

.appliance-tab-topline {
  gap: 8px;
  min-width: 0;
}

.appliance-tab-name {
  display: block;
  font-size: var(--font-size-14);
  font-weight: 600;
}

.appliance-tab-meta {
  display: block;
  font-size: var(--font-size-11);
  color: var(--font-tip-color);
}

.appliance-tab-aside {
  gap: 8px;
}

.appliance-tab-status {
  display: inline-flex;
  gap: 2px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: var(--font-size-11);
  color: var(--font-main-color);
  background: var(--color-successBg);

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--color-success);
  }
}

.appliance-tab-chevron {
  width: 10px;
  height: 10px;
  border-right: 2px solid var(--font-tip-color);
  border-bottom: 2px solid var(--font-tip-color);
  transform: rotate(45deg);
  transition: transform 0.2s ease;
}

.appliance-tab-chevron.active {
  transform: rotate(225deg);
}

.detail-section {
  padding: 0 10px 10px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.detail-item {
  padding: 8px 10px;
  border-radius: 12px;
  background: var(--surface-card-bg);
  border: 1px solid var(--border-primary);
}

.detail-item.primary {
  background: var(--surface-card-bg-strong);
}

.detail-item.full-width {
  grid-column: 1 / -1;
}

.detail-item-label {
  font-size: var(--font-size-11);
  color: var(--font-tip-color);
}

.detail-item-value {
  margin-top: 4px;
  font-size: var(--font-size-13);
  font-weight: 600;
}

.menu-empty-state {
  min-height: 220px;
}

.monitor-pane {
  width: 100%;
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
  transition:
    max-height 0.24s ease,
    opacity 0.2s ease;
}

.monitor-pane.open {
  max-height: 960px;
  opacity: 1;
  pointer-events: auto;
}

.monitor-trigger {
  position: absolute;
  display: inline-flex;
  left: -16px;
  bottom: 200px;
  z-index: 3;
  width: 38px;
  height: 52px;
  padding: 0;
  border: 1px solid
    color-mix(in srgb, var(--color-primary) 18%, var(--border-main-color) 82%);
  border-left: none;
  border-radius: 0 16px 16px 0;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--bg-content-color) 98%, transparent) 0%,
    color-mix(in srgb, var(--color-primaryBg) 24%, var(--bg-content-color) 76%)
      100%
  );
  color: var(--color-primary);
  box-shadow: -10px 14px 30px var(--bg-gradient-shadow);
  backdrop-filter: blur(14px);
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease,
    color 0.2s ease,
    border-color 0.2s ease,
    background 0.2s ease;
}

.monitor-trigger::before {
  content: "";
  position: absolute;
  right: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--color-primary) 78%, var(--color-white) 22%) 0%,
    var(--color-primary) 100%
  );
  opacity: 0.9;
}

.monitor-trigger:hover {
  transform: translateX(4px);
  border-color: color-mix(
    in srgb,
    var(--color-primary) 34%,
    var(--border-main-color) 66%
  );
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--bg-content-color) 100%, transparent) 0%,
    color-mix(in srgb, var(--color-primaryBg) 34%, var(--bg-content-color) 66%)
      100%
  );
  color: var(--color-primary-hover);
  box-shadow: -14px 18px 32px var(--bg-gradient-shadow);
}

.monitor-trigger-icon {
  position: relative;
  width: 100%;
  height: 100%;
  padding-left: 3px;
  font-size: 18px;
  line-height: 1;
}

@media (max-width: 768px) {
  .appliance-tab-trigger {
    grid-template-columns: 8px minmax(0, 1fr);
  }

  .appliance-tab-aside {
    justify-content: flex-start;
  }

  .appliance-tab-status {
    justify-self: flex-start;
  }

  .detail-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1280px) {
  .appliance-menu {
    min-height: 420px;
  }
}
</style>
