// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

export const enTranslations = {
  // ── Brand / App ──────────────────────────────────────────────────────────
  appBrand:            'VMS Analytics Suite',
  appTitle:            'VMS Dashboard',
  appVersion:          'v2.1.0-oep',
  appPlatform:         'Platform',

  // ── Navigation ───────────────────────────────────────────────────────────
  navCameraDiscovery:   'Camera Discovery',
  navAnalyticsEngine:   'Analytics Engine Config',
  navCameraDesc:        'Discover & manage cameras',
  navAnalyticsDesc:     'Analytics app & event pipeline',
  navNavigation:        'Navigation',
  navPipelineActive:    'Pipeline Active',

  // ── Breadcrumbs / Page headers ────────────────────────────────────────────
  breadcrumbRoot:         'VMS Dashboard',
  breadcrumbCameras:      'Camera Discovery',
  breadcrumbAnalytics:    'Analytics Engine',
  pageHeaderCameras:      'Camera Discovery',
  pageHeaderAnalytics:    'Analytics Engine Configuration',

  // ── Status badges ─────────────────────────────────────────────────────────
  statusOnline:    'Online',
  statusOffline:   'Offline',
  statusUnknown:   'Unknown',
  statusEnabled:   'enabled',
  statusConnected: 'Connected',
  statusDegraded:  'Degraded',
  statusOfflineEngine: 'Offline',
  statusChecking:  'Checking…',

  // ── Stat cards ────────────────────────────────────────────────────────────
  statConnectedNvrs:    'Connected NVRs',
  statDiscoveredCams:   'Discovered Cameras',
  statEnabledCams:      'Enabled Cameras',
  statActiveAnalyticsApp:    'Active Analytics App',

  // ── Camera Discovery panel ────────────────────────────────────────────────
  cameraPanelTitle:         'Camera Discovery',
  cameraDiscover:           'Discover Cameras',
  cameraRediscover:         'Rediscover',
  cameraDiscovering:        'Discovering…',
  cameraDiscoverHint:       'Run discovery to populate cameras from connected NVRs',
  cameraColId:              'Camera ID',
  cameraColName:            'Camera Name',
  cameraColVendor:          'Vendor',
  cameraColStatus:          'Status',
  cameraColEnabled:         'Enabled',
  cameraEnable:             'Enable',
  cameraNoResults:          'No cameras discovered yet.',
  cameraEmptyDiscovery:     'Run discovery to populate cameras from connected NVRs',

  // ── Analytics Engine panel ────────────────────────────────────────────────
  enginePanelTitle:        'Analytics Engine Configuration',
  engineAnalyticsAppLabel:      'Analytics App',
  engineGlobalCapsLabel:   'Global Capabilities',
  engineOpenConfig:        'Configure',
  engineEnableLabels:      'Enable Labels',
  engineEnableBookmarks:   'Enable Bookmarks',
  engineEnableAcknowledge: 'Enable Acknowledge',
  engineEnableTriggerRec:  'Enable Trigger Recording',

  // ── Analytics App descriptions ─────────────────────────────────────────────────
  analyticsAppVideoSearch:          'Video Search',
  analyticsAppVideoSearchDesc:      'Semantic query-based search and clip retrieval from recorded footage',
  analyticsAppVideoSummarization:   'Video Summarization',
  analyticsAppVideoSummDesc:        'Real-time AI video summarization using Intel OpenVINO',
  analyticsAppObjectDetection:      'Object Detection',
  analyticsAppObjectDetectionDesc:  'Real-time AI object classification with bounding boxes via Intel OpenVINO',
  analyticsAppLiveCaptioning:       'Live Video Captioning',
  analyticsAppLiveCaptioningDesc:   'Real-time VLM inference on live RTSP streams via DL Streamer + WebRTC',

  // ── Metadata / Events panel ───────────────────────────────────────────────
  eventsPanelTitle:        'Metadata Events',
  eventsRefresh:           'Refresh Events',
  eventsLoading:           'Loading…',
  eventsColEventId:        'Event ID',
  eventsColTimestamp:      'Timestamp',
  eventsColCamera:         'Camera Name',
  eventsColType:           'Event Type',
  eventsColVendor:         'Vendor',
  eventsRunAnalysis:       'Analyse',
  eventsRunAnalysisTitle:  'Run analysis pipeline on this event',
  eventsEmptyEnabled:      'Waiting for events from folder watchdog…',
  eventsEmptyDisabled:     'Enable a camera to start receiving events',
  eventsEmptyHint:         'Enable a camera and events will appear here as the folder watchdog picks them up',

  // ── Analysis Results panel ────────────────────────────────────────────────
  resultsPanelTitle:       'Analysis Results',
  resultsTabResults:       'Results',
  resultsTabCommands:      'Commands',
  resultsPending:          'Analysing…',
  resultsColCamera:        'Camera',
  resultsColApp:           'App',
  resultsColConfidence:    'Confidence',
  resultsColDisposition:   'Status',
  resultsColClipUrl:       'Clip URL',
  resultsColBBox:          'BBox',
  resultsColCount:         'Count',
  resultsColClass:         'Class',
  resultsColEventId:       'Event ID',
  resultsColCommand:       'Command',
  resultsColVendor:        'Vendor',
  resultsColStatus:        'Status',
  resultsColNotes:         'Notes',
  resultsEmpty:            'No analysis results yet.',

  // ── Analytics Config Modal ────────────────────────────────────────────────
  modalTitle:              'Analytics Configuration',
  modalAnalyticsAppSection:     'Analytics Application',
  modalGlobalSection:      'Global Capabilities',
  modalAppConfigSection:   'App-Specific Config',
  modalSave:               'Save Configuration',
  modalCancel:             'Cancel',

  modalVideoSearch:        'Video Search',
  modalVideoSearchDesc:    'Video Search & Retrieval',
  modalVideoSumm:          'Video Summarization',
  modalObjectDetection:    'Object Detection',
  modalObjectDetectionDesc: 'Real-time AI object classification',

  modalEnableLabels:       'Enable Labels',
  modalEnableLabelDesc:    'Push label to VMS',
  modalEnableBookmarks:    'Enable Bookmarks',
  modalEnableBookmarkDesc: 'Create bookmark in VMS',
  modalEnableAcknowledge:  'Enable Acknowledge',
  modalEnableAckDesc:      'Acknowledge event in VMS',
  modalEnableTriggerRec:   'Enable Trigger Recording',
  modalEnableTriggerDesc:  'Trigger recording clip in VMS',

  // Video Search config fields
  cfgSearchQuery:          'Search Query',
  cfgSearchQueryHint:      'Natural language or keyword query sent to the Analytics App',
  cfgMaxClips:             'Max Clips Returned',
  cfgMaxClipsHint:         'Max matching clips returned per event',

  // Video Summarization config fields
  cfgSummaryLength:        'Summary Length',
  cfgSummaryBrief:         'Brief (1–2 sentences)',
  cfgSummaryStandard:      'Standard (3–5 sentences)',
  cfgSummaryDetailed:      'Detailed (full paragraph)',
  cfgExtractKeyEvents:     'Extract Key Events',
  cfgExtractKeyEventsHint: 'Pull notable scene changes into a structured list',
  cfgSceneSensitivity:     'Scene Change Sensitivity',
  cfgSceneSensitivityHint: 'Minimum visual difference to declare a new scene',

  // Object Detection config fields
  cfgTargetClasses:        'Target Classes',
  cfgMaxDetections:        'Max Detections',
  cfgMaxDetectionsHint:    'Per-frame detection cap',

  // ── API Log Drawer ────────────────────────────────────────────────────────
  apiLogTitle:             'API Log',
  apiLogEmpty:             'No API calls recorded yet.',
  apiLogCalls:             'calls',

  // ── Toast / Notification messages ────────────────────────────────────────
  toastDiscoverSuccess:    'Discovered {{count}} cameras via IVmsShim',
  toastDiscoverFailed:     'Discovery failed: {{message}}',
  toastCameraEnabled:      'Camera "{{name}}" enabled',
  toastCameraDisabled:     'Camera "{{name}}" disabled',
  toastCameraToggleFailed: 'Failed to {{action}} camera: {{message}}',
  toastAnalyticsAppSwitched:    'Analytics App switched to "{{name}}"',
  toastConfigSaved:        '"{{name}}" configuration saved',
  toastEventSent:          'Event {{id}} sent to "{{app}}"',
  toastAnalysisComplete:   '{{app}} analysis complete: {{id}} ({{conf}}%)',
  toastAsyncResult:        'Async result: {{id}} ({{conf}}%)',

  // ── Vendor names ──────────────────────────────────────────────────────────
  vendorFrigate:    'Frigate',
  vendorNxWitness:  'Nx Witness',

  // ── Common ────────────────────────────────────────────────────────────────
  cancel:    'Cancel',
  save:      'Save',
  close:     'Close',
  loading:   'Loading…',
  notSupported: 'Not supported',
  accepted:     'accepted',
  unsupported:  'unsupported',
};
