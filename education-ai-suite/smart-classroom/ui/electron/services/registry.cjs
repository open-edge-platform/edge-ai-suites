// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Static description of every Smart Classroom process the manager knows about.
//
// This table is the security boundary for service IPC: the renderer may only
// reference ids defined here and never supplies a command, argument or port.
//
// `managed`  - the manager spawns and kills it.
// `ownedBy`  - spawned by another service (main.py -> content_search/start_services.py,
//              GradingFeature.build(); start_services.py -> chroma/preprocess/ingest).
//              Lifecycle follows the owner; we only observe health and logs.

const path = require('path');
const paths = require('./paths.cjs');
const config = require('./config-store.cjs');

const HOST = '127.0.0.1';

// Content search boots when any of its three consumer features is on
const contentSearchEnabled = () =>
  config.featureEnabled('content_search') ||
  config.featureEnabled('topic_segmentation') ||
  config.featureEnabled('qa');

const gradingEnabled = () => config.featureEnabled('grading');

const SERVICES = [
  {
    id: 'backend',
    label: 'Backend API',
    port: 8000,
    healthUrl: `http://${HOST}:8000/health`,
    managed: true,
    command: () => paths.venvPython(),
    args: () => ['main.py'],
    cwd: () => paths.home(),
    enabled: () => true,
    description: 'FastAPI app (main.py). Starts content search, layout detection and grading.',
  },
  {
    id: 'content-search',
    label: 'Content Search',
    port: 9011,
    healthUrl: `http://${HOST}:9011/api/v1/system/health`,
    // This endpoint fans out to the DB and every downstream service, so it is
    // far slower to answer than a plain liveness probe.
    healthTimeoutMs: 8000,
    managed: false,
    ownedBy: 'backend',
    logTags: ['main_app', 'launcher'],
    enabled: contentSearchEnabled,
    description: 'content_search/start_services.py, spawned by the backend.',
  },
  {
    id: 'chroma',
    label: 'ChromaDB',
    port: 9090,
    managed: false,
    ownedBy: 'content-search',
    logTags: ['chromadb'],
    enabled: contentSearchEnabled,
    description: 'Vector store for content search embeddings.',
  },
  {
    id: 'video-preprocess',
    label: 'Video Preprocess',
    port: 8001,
    managed: false,
    ownedBy: 'content-search',
    logTags: ['preprocess'],
    enabled: contentSearchEnabled,
    description: 'Frame extraction and VLM video summarisation.',
  },
  {
    id: 'file-ingest',
    label: 'File Ingest',
    port: 9990,
    managed: false,
    ownedBy: 'content-search',
    logTags: ['ingest'],
    enabled: contentSearchEnabled,
    description: 'Document/media ingestion and embedding.',
  },
  {
    id: 'layout-detection',
    label: 'Layout Detection',
    port: 9902,
    managed: false,
    ownedBy: 'backend',
    logTags: ['layout_detection'],
    enabled: gradingEnabled,
    description: 'Document layout model service used by grading.',
  },
  {
    id: 'grading',
    label: 'Grading (VLM)',
    port: 9012,
    managed: false,
    ownedBy: 'backend',
    logTags: ['grading'],
    enabled: gradingEnabled,
    description: 'Vision-language grading service.',
  },
];

const BY_ID = new Map(SERVICES.map((service) => [service.id, service]));

// start_services.py and grading_feature.py tee child output into the backend's
// stdout as `[<name>] <line>`, so the tag is what tells us which service a line
// actually belongs to.
const BY_LOG_TAG = new Map();
for (const service of SERVICES) {
  for (const tag of service.logTags || []) BY_LOG_TAG.set(tag, service.id);
}

// Lowercase-only tag: the backend's own logging format starts with a timestamp
// or an uppercase level, so it never matches.
const LOG_TAG_PATTERN = /^\[([a-z_]+)\] ?(.*)$/;

function routeLogLine(text) {
  const match = LOG_TAG_PATTERN.exec(text);
  if (!match) return null;
  const id = BY_LOG_TAG.get(match[1]);
  return id ? { id, text: match[2] } : null;
}

function get(id) {
  return typeof id === 'string' ? BY_ID.get(id) : undefined;
}

// Ports belonging to `id` and everything it (transitively) owns. Used to scope
// the post-kill port sweep so unrelated python processes are never touched.
function ownedPorts(id) {
  const ports = [];
  const walk = (currentId) => {
    const service = get(currentId);
    if (service?.port) ports.push(service.port);
    for (const child of SERVICES) {
      if (child.ownedBy === currentId) walk(child.id);
    }
  };
  walk(id);
  return [...new Set(ports)];
}

// Serialisable view for the renderer: no functions, no absolute commands.
function describe(service) {
  return {
    id: service.id,
    label: service.label,
    port: service.port ?? null,
    managed: !!service.managed,
    ownedBy: service.ownedBy ?? null,
    description: service.description,
    enabled: service.enabled(),
  };
}

module.exports = {
  SERVICES,
  get,
  ownedPorts,
  describe,
  routeLogLine,
  list: () => SERVICES.map(describe),
  resolveCommand: (service) => ({
    command: service.command(),
    args: service.args(),
    cwd: service.cwd(),
    display: `${path.basename(service.command())} ${service.args().join(' ')}`,
  }),
};
