// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Environment repair for a long-running process on Windows.
//
// A process inherits its environment once, at launch. Installers write the new
// PATH to the registry and broadcast WM_SETTINGCHANGE, which only shells act
// on — so a tool installed while this app is running stays invisible to it, and
// to every child it spawns, until the app is restarted. Re-reading the registry
// here is what makes "Install" followed by "Check" work in one session.

const { execFile } = require('child_process');

const REG = {
  machineEnv: 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment',
  userEnv: 'HKCU\\Environment',
  dlStreamer: 'HKLM\\SOFTWARE\\Intel\\dlstreamer',
};

const isWindows = process.platform === 'win32';

function run(file, args, timeout = 15000) {
  return new Promise((resolve) => {
    execFile(file, args, { timeout, windowsHide: true, maxBuffer: 1 << 22 }, (error, stdout) => {
      resolve({ ok: !error, stdout: (stdout || '').trim() });
    });
  });
}

/** One registry value as a string, or null when the key or value is absent. */
async function regValue(key, name) {
  const result = await run('reg.exe', ['query', key, '/v', name]);
  if (!result.ok) return null;
  // reg prints "    <name>    REG_SZ    <value>"; the value may contain spaces.
  const pattern = new RegExp(`\\b${name}\\s+REG_(?:EXPAND_)?SZ\\s+([^\\r\\n]+)`, 'i');
  const match = result.stdout.match(pattern);
  return match ? match[1].trim() : null;
}

/** Expand %VAR% references against the current environment, as the shell would. */
function expand(value) {
  return value.replace(/%([^%]+)%/g, (all, name) => process.env[name] ?? all);
}

const normalise = (entry) => entry.replace(/[\\/]+$/, '').toLowerCase();

function splitPath(value) {
  return (value || '')
    .split(';')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

/**
 * Merge the machine and user PATH from the registry into process.env.PATH.
 *
 * Live entries are kept: they include anything set for this process alone (the
 * DL Streamer directories below, npm shims, a developer's shell). Registry
 * entries go first so a freshly installed tool wins over a stale copy.
 *
 * @returns {Promise<string[]>} the entries this call added, for logging.
 */
async function refreshPath() {
  if (!isWindows) return [];

  const fromRegistry = [];
  for (const key of [REG.machineEnv, REG.userEnv]) {
    const value = await regValue(key, 'Path');
    if (value) fromRegistry.push(...splitPath(value).map(expand));
  }
  if (!fromRegistry.length) return [];

  const live = splitPath(process.env.PATH);
  const seen = new Set();
  const merged = [];
  for (const entry of [...fromRegistry, ...live]) {
    const key = normalise(entry);
    if (seen.has(key)) continue;
    seen.add(key);
    merged.push(entry);
  }

  const known = new Set(live.map(normalise));
  const added = fromRegistry.filter((entry) => !known.has(normalise(entry)));

  process.env.PATH = merged.join(';');
  return [...new Set(added)];
}

/**
 * Where DL Streamer is installed, from the key its installer writes.
 */
async function dlStreamerInstall() {
  if (!isWindows) return null;
  const [version, installDir] = await Promise.all([
    regValue(REG.dlStreamer, 'Version'),
    regValue(REG.dlStreamer, 'InstallDir'),
  ]);
  if (!version && !installDir) return null;
  return { version, installDir: installDir ? expand(installDir) : null };
}

/**
 * Apply the environment DL Streamer needs, so the backend and any gst-* helper
 * inherit it.
 *
 * @returns {Promise<{installDir: string, pluginPath: string, gstBinDir: string|null}|null>}
 *   null when DL Streamer is not installed or the install is incomplete.
 */
async function applyDlStreamerEnv() {
  const install = await dlStreamerInstall();
  if (!install?.installDir) return null;

  const path = require('path');
  const fs = require('fs');
  const installDir = install.installDir.replace(/[\\/]+$/, '');
  const pluginPath = path.join(installDir, 'bin');
  if (!fs.existsSync(pluginPath)) return null;

  // The GStreamer runtime DL Streamer builds against, recorded by its installer.
  const gstRoot = await regValue(REG.machineEnv, 'GSTREAMER_1_0_ROOT_MSVC_X86_64');
  const gstBinDir = gstRoot ? path.join(expand(gstRoot).replace(/[\\/]+$/, ''), 'bin') : null;

  process.env.DLSTREAMER_DIR = installDir;
  process.env.GST_PLUGIN_PATH = pluginPath;

  const prepend = [pluginPath, ...(gstBinDir ? [gstBinDir] : [])];
  const rest = splitPath(process.env.PATH).filter(
    (entry) => !prepend.some((dir) => normalise(dir) === normalise(entry))
  );
  process.env.PATH = [...prepend, ...rest].join(';');

  return { installDir, pluginPath, gstBinDir };
}

module.exports = { refreshPath, dlStreamerInstall, applyDlStreamerEnv };
