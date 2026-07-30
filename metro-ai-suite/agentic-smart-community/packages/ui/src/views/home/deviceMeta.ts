// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
type Translate = (key: string) => string;

export const KNOWN_SMART_HOME_SOURCE_IDS = [
  "cam_fridge",
  "cam_child",
  "cam_elder_bedroom",
  "cam_elder_bedroom_2",
] as const;

export type KnownSmartHomeSourceId =
  (typeof KNOWN_SMART_HOME_SOURCE_IDS)[number];

export interface SmartHomeSourceMeta {
  id: string;
  name?: string;
  location: string;
  cameraLabel: string;
  liveTitle: string;
  liveDescription: string;
}

const buildDefaultMeta = (
  sourceId: string,
  t: Translate,
): SmartHomeSourceMeta => ({
  id: sourceId,
  location: t("smartHome.elderlyCareLocation"),
  cameraLabel: sourceId,
  liveTitle: t("smartHome.liveGenericView"),
  liveDescription: t("smartHome.liveGenericMonitoringDescription"),
});

export const getSmartHomeSourceMeta = (
  sourceId: string,
  t: Translate,
): SmartHomeSourceMeta => {
  switch (sourceId) {
    case "cam_fridge":
      return {
        id: sourceId,
        location: t("smartHome.fridgeLocationKitchen"),
        cameraLabel: t("smartHome.fridgeCamera"),
        liveTitle: t("smartHome.liveFridgeView"),
        liveDescription: t("smartHome.liveMonitoringDescription"),
      };
    case "cam_child":
      return {
        id: sourceId,
        location: t("smartHome.childCustodyLocation"),
        cameraLabel: t("smartHome.childCustodyCamera"),
        liveTitle: t("smartHome.liveChildCustodyView"),
        liveDescription: t("smartHome.childCustodyMonitoringDescription"),
      };
    case "cam_elder_bedroom":
      return {
        id: sourceId,
        location: t("smartHome.elderlyCareLocation"),
        cameraLabel: t("smartHome.elderlyCareCamera"),
        liveTitle: t("smartHome.liveElderlyCareView"),
        liveDescription: t("smartHome.elderlyCareMonitoringDescription"),
      };
    case "cam_elder_bedroom_2":
      return {
        id: sourceId,
        location: t("smartHome.elderlyCareLocation"),
        cameraLabel: t("smartHome.elderlyCareCamera"),
        liveTitle: t("smartHome.liveElderlyCareView"),
        liveDescription: t("smartHome.elderlyCareMonitoringDescription"),
      };
    default:
      return buildDefaultMeta(sourceId, t);
  }
};
