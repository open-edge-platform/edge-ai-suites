// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
type Translate = (key: string) => string;

export const KNOWN_SMART_BUILDING_SOURCE_IDS = [
  "cam_fridge",
  "cam_child",
  "cam_elder_bedroom",
  "cam_elder_bedroom_2",
] as const;

export type KnownSmartBuildingSourceId =
  (typeof KNOWN_SMART_BUILDING_SOURCE_IDS)[number];

export interface SmartBuildingSourceMeta {
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
): SmartBuildingSourceMeta => ({
  id: sourceId,
  location: t("smartBuilding.elderlyCareLocation"),
  cameraLabel: sourceId,
  liveTitle: t("smartBuilding.liveGenericView"),
  liveDescription: t("smartBuilding.liveGenericMonitoringDescription"),
});

export const getSmartBuildingSourceMeta = (
  sourceId: string,
  t: Translate,
): SmartBuildingSourceMeta => {
  switch (sourceId) {
    case "cam_fridge":
      return {
        id: sourceId,
        location: t("smartBuilding.fridgeLocationKitchen"),
        cameraLabel: t("smartBuilding.fridgeCamera"),
        liveTitle: t("smartBuilding.liveFridgeView"),
        liveDescription: t("smartBuilding.liveMonitoringDescription"),
      };
    case "cam_child":
      return {
        id: sourceId,
        location: t("smartBuilding.childCustodyLocation"),
        cameraLabel: t("smartBuilding.childCustodyCamera"),
        liveTitle: t("smartBuilding.liveChildCustodyView"),
        liveDescription: t("smartBuilding.childCustodyMonitoringDescription"),
      };
    case "cam_elder_bedroom":
      return {
        id: sourceId,
        location: t("smartBuilding.elderlyCareLocation"),
        cameraLabel: t("smartBuilding.elderlyCareCamera"),
        liveTitle: t("smartBuilding.liveElderlyCareView"),
        liveDescription: t("smartBuilding.elderlyCareMonitoringDescription"),
      };
    case "cam_elder_bedroom_2":
      return {
        id: sourceId,
        location: t("smartBuilding.elderlyCareLocation"),
        cameraLabel: t("smartBuilding.elderlyCareCamera"),
        liveTitle: t("smartBuilding.liveElderlyCareView"),
        liveDescription: t("smartBuilding.elderlyCareMonitoringDescription"),
      };
    default:
      return buildDefaultMeta(sourceId, t);
  }
};
