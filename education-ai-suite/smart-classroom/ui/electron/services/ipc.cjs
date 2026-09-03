// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// IPC surface for service management.
//
// Everything crossing this boundary is validated: the sender must be the app's
// own window, and the only accepted argument is a service id that exists in the
// registry. The renderer can never supply a command, path or port.

const { ipcMain, shell, dialog, clipboard } = require('electron');
const config = require('./config-store.cjs');
const paths = require('./paths.cjs');
const registry = require('./registry.cjs');
const { LOG_ID: setupLogId } = require('./setup-runner.cjs');

function ok(data) {
  return { ok: true, data };
}

function fail(error) {
  // Message only — stacks and absolute paths stay in the main process log.
  return { ok: false, error: error instanceof Error ? error.message : String(error) };
}

function register({ manager, logs, setup, getWindow }) {
  const trusted = (event) => {
    const window = getWindow();
    return !!window && !window.isDestroyed() && event.sender.id === window.webContents.id;
  };

  const serviceId = (value) => {
    if (!registry.get(value)) throw new Error(`Unknown service: ${String(value).slice(0, 64)}`);
    return value;
  };

  const handle = (channel, handler) => {
    ipcMain.handle(channel, async (event, ...args) => {
      if (!trusted(event)) return fail('Rejected: untrusted sender.');
      try {
        return ok(await handler(...args));
      } catch (error) {
        return fail(error);
      }
    });
  };

  handle('services:list', () => manager.snapshot());
  handle('services:start', (id) => manager.startService(serviceId(id)));
  handle('services:stop', (id) => manager.stopService(serviceId(id)));
  handle('services:restart', (id) => manager.restartService(serviceId(id)));

  handle('logs:read', (id, options) => {
    const limit = Math.min(Math.max(Number(options?.limit) || 1000, 1), 5000);
    const sinceSeq = Math.max(Number(options?.sinceSeq) || 0, 0);
    return logs.read(serviceId(id), { limit, sinceSeq });
  });

  handle('logs:clear', (id) => {
    logs.clear(serviceId(id));
    return true;
  });

  handle('logs:reveal', (id) => {
    const file = logs.logFile(serviceId(id));
    if (file) shell.showItemInFolder(file);
    else shell.openPath(paths.managerLogDir());
    return file;
  });

  // config-store validates every path against the schema allowlist.
  handle('config:describe', () => config.describe());
  handle('config:apply', (changes) => config.apply(changes));
  handle('config:reveal', () => {
    shell.showItemInFolder(paths.configFile());
    return paths.configFile();
  });

  // Setup steps are named by id only; the runner owns every command line.
  handle('setup:list', () => ({ sections: setup.sections(), steps: setup.snapshot() }));
  handle('setup:check', () => setup.checkAll());
  handle('setup:run', async (stepId, actionId) => {
    // Validates both ids and throws before anything runs.
    const { step, action } = setup.find(stepId, actionId);
    if (action.destructive) {
      const window = getWindow();
      const options = {
        type: 'warning',
        title: 'Smart Classroom',
        message: `${action.label} the ${step.label.toLowerCase()}?`,
        detail: `${paths.venvDir()}\n\nThis folder will be deleted and every package reinstalled, which takes several minutes and needs network access.`,
        buttons: ['Cancel', `${action.label} and reinstall`],
        defaultId: 0,
        cancelId: 0,
      };
      const { response } = window ? await dialog.showMessageBox(window, options) : await dialog.showMessageBox(options);
      if (response !== 1) return { cancelled: true };
    }
    return setup.runStep(stepId, actionId);
  });
  handle('setup:cancel', () => setup.cancel());
  handle('setup:logs', (options) => {
    const limit = Math.min(Math.max(Number(options?.limit) || 1000, 1), 5000);
    return logs.read(setupLogId, { limit });
  });
  handle('setup:clearLogs', () => {
    logs.clear(setupLogId);
    return true;
  });
  handle('setup:revealLogs', () => {
    // The sink only holds a file while a step is running; fall back to the folder.
    const file = logs.logFile(setupLogId);
    if (file) shell.showItemInFolder(file);
    else shell.openPath(paths.managerLogDir());
    return file;
  });

  // Diagnostics for a bug report. Renderer-composed, but copied here.
  handle('app:copyText', (text) => {
    if (typeof text !== 'string') throw new Error('Nothing to copy.');
    clipboard.writeText(text.slice(0, 100000));
    return true;
  });

  const send = (channel, payload) => {
    const window = getWindow();
    if (window && !window.isDestroyed()) window.webContents.send(channel, payload);
  };

  manager.on('changed', (snapshot) => send('services:changed', snapshot));
  setup.on('changed', (snapshot) => send('setup:changed', snapshot));
  logs.on('append', (batch) => send('logs:append', batch));
}

module.exports = { register };
