// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
type Translate = (key: string) => string;

export const KNOWN_SMART_COMMUNITY_SOURCE_IDS = [
  "cam_fridge",
  "cam_child",
  "cam_elder_bedroom",
  "cam_elder_bedroom_2",
] as const;

export type KnownSmartCommunitySourceId =
  (typeof KNOWN_SMART_COMMUNITY_SOURCE_IDS)[number];

export interface SmartCommunitySourceMeta {
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
): SmartCommunitySourceMeta => ({
  id: sourceId,
  location: t("smartCommunity.elderlyCareLocation"),
  cameraLabel: sourceId,
  liveTitle: t("smartCommunity.liveGenericView"),
  liveDescription: t("smartCommunity.liveGenericMonitoringDescription"),
});

export const getSmartCommunitySourceMeta = (
  sourceId: string,
  t: Translate,
): SmartCommunitySourceMeta => {
  switch (sourceId) {
    case "cam_fridge":
      return {
        id: sourceId,
        location: t("smartCommunity.fridgeLocationKitchen"),
        cameraLabel: t("smartCommunity.fridgeCamera"),
        liveTitle: t("smartCommunity.liveFridgeView"),
        liveDescription: t("smartCommunity.liveMonitoringDescription"),
      };
    case "cam_child":
      return {
        id: sourceId,
        location: t("smartCommunity.childCustodyLocation"),
        cameraLabel: t("smartCommunity.childCustodyCamera"),
        liveTitle: t("smartCommunity.liveChildCustodyView"),
        liveDescription: t("smartCommunity.childCustodyMonitoringDescription"),
      };
    case "cam_elder_bedroom":
      return {
        id: sourceId,
        location: t("smartCommunity.elderlyCareLocation"),
        cameraLabel: t("smartCommunity.elderlyCareCamera"),
        liveTitle: t("smartCommunity.liveElderlyCareView"),
        liveDescription: t("smartCommunity.elderlyCareMonitoringDescription"),
      };
    case "cam_elder_bedroom_2":
      return {
        id: sourceId,
        location: t("smartCommunity.elderlyCareLocation"),
        cameraLabel: t("smartCommunity.elderlyCareCamera"),
        liveTitle: t("smartCommunity.liveElderlyCareView"),
        liveDescription: t("smartCommunity.elderlyCareMonitoringDescription"),
      };
    default:
      return buildDefaultMeta(sourceId, t);
  }
};
