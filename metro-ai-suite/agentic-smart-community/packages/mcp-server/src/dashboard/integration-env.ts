// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

export interface DashboardIntegrationConfig {
  routerUrl?: URL;
  openClawGatewayUrl?: URL;
  openClawGatewayToken?: string;
}

function readHttpUrl(name: string): URL | undefined {
  const value = process.env[name]?.trim();
  if (!value) return undefined;
  const url = new URL(value);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`${name} must use http or https`);
  }
  return url;
}

export function loadDashboardIntegrationConfig(): DashboardIntegrationConfig {
  return {
    routerUrl: readHttpUrl("SMARTBUILDING_ROUTER_URL"),
    openClawGatewayUrl: readHttpUrl("SMARTBUILDING_OPENCLAW_GATEWAY_URL"),
    openClawGatewayToken: process.env.SMARTBUILDING_OPENCLAW_GATEWAY_TOKEN?.trim() || undefined,
  };
}