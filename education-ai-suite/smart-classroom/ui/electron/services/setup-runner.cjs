// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// First-run setup: the checks and installs driven from the app.
//
// A step reports one status and offers zero or more named actions. Everything is
// idempotent, so an interrupted run can simply be started again. The renderer can
// only name a step and an action defined here; it never supplies a command line.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn, execFile } = require('child_process');
const { EventEmitter } = require('events');

const paths = require('./paths.cjs');
const config = require('./config-store.cjs');
const registry = require('./registry.cjs');
const proc = require('./win-proc.cjs');
const winEnv = require('./win-env.cjs');

const LOG_ID = 'setup';
const MIN_RAM_GB = 32;
const RAM_TOLERANCE = 0.95;
const MIN_DISK_GB = 50;
const PYTHON_TARGET = [3, 12];
const LATEST_GPU_DRIVER = '32.0.101.8826';
const LATEST_NPU_DRIVER = '32.0.100.4778';
const REQUIRED_DLSTREAMER = '2026.1.0';
const NPU_DRIVER_URL = 'https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html';
const DLSTREAMER_URL =
  'https://github.com/open-edge-platform/dlstreamer/releases/download/v2026.1.0/dlstreamer-2026.1.0-win64.exe';

const STATUS = {
  UNKNOWN: 'unknown',
  OK: 'ok',
  WARN: 'warn',
  MISSING: 'missing',
  RUNNING: 'running',
  FAILED: 'failed',
};

const SECTIONS = [
  { id: 'system', label: 'System and drivers' },
  { id: 'software', label: 'Software and environment' },
];

// Most actions install or create something, so they are pointless once the step
// is satisfied. Actions that stay useful afterwards override this.
const visibleUnlessOk = (status) => status !== STATUS.OK;

function run(file, args, timeout = 20000) {
  return new Promise((resolve) => {
    execFile(file, args, { timeout, windowsHide: true }, (error, stdout, stderr) => {
      resolve({ ok: !error, stdout: (stdout || '').trim(), stderr: (stderr || '').trim() });
    });
  });
}

const gb = (bytes) => Math.round((bytes / 1024 ** 3) * 10) / 10;

/** -1, 0 or 1, comparing dotted numeric versions of any length. */
function compareVersions(a, b) {
  const left = String(a).split('.').map(Number);
  const right = String(b).split('.').map(Number);
  for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
    const diff = (left[i] || 0) - (right[i] || 0);
    if (diff) return diff > 0 ? 1 : -1;
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Detection helpers
// ---------------------------------------------------------------------------

// pnputil localises its field labels, so match on the values (Intel device names,
// oemNN.inf, dotted versions) rather than on label text.
async function pnputilDevice(className, pattern) {
  const result = await run('pnputil.exe', ['/enum-devices', '/class', className, '/connected'], 30000);
  if (!result.ok) return null;
  for (const block of result.stdout.split(/\r?\n\s*\r?\n/)) {
    const name = block.match(pattern);
    if (!name) continue;
    return { name: name[0].trim(), inf: (block.match(/oem\d+\.inf/i) || [])[0] ?? null };
  }
  return null;
}

async function driverVersionFor(inf) {
  if (!inf) return null;
  const result = await run('pnputil.exe', ['/enum-drivers'], 30000);
  if (!result.ok) return null;
  for (const block of result.stdout.split(/\r?\n\s*\r?\n/)) {
    if (!block.toLowerCase().includes(inf.toLowerCase())) continue;
    const version = block.match(/\b(\d+\.\d+\.\d+\.\d+)\b/);
    if (version) return version[1];
  }
  return null;
}

function describeDriver(label, installed, latest) {
  if (!installed) return { status: STATUS.OK, detail: `${label} (driver version unavailable)` };
  if (compareVersions(installed, latest) >= 0) {
    return { status: STATUS.OK, detail: `${label}, driver ${installed}` };
  }
  return { status: STATUS.WARN, detail: `${label}, driver ${installed}; ${latest} is newer` };
}

async function pythonCandidates() {
  const found = [];
  const launcher = await run('py.exe', ['-0p']);
  if (launcher.ok) {
    for (const line of launcher.stdout.split(/\r?\n/)) {
      const match = line.match(/(\S:\\[^\r\n]*python\.exe)/i);
      if (match) found.push(match[1]);
    }
  }
  const where = await run('where.exe', ['python']);
  if (where.ok) {
    for (const line of where.stdout.split(/\r?\n/)) {
      // The Microsoft Store alias is a stub that opens the Store instead of running.
      if (line.trim() && !line.includes('WindowsApps')) found.push(line.trim());
    }
  }
  return [...new Set(found)];
}

async function pythonVersion(exe) {
  const result = await run(exe, ['-c', 'import sys;print("%d.%d.%d" % sys.version_info[:3])']);
  return result.ok ? result.stdout : null;
}

/** The interpreter used to create the venv: prefers an exact 3.12 match. */
async function findPython() {
  for (const exe of await pythonCandidates()) {
    const version = await pythonVersion(exe);
    if (!version) continue;
    const [major, minor] = version.split('.').map(Number);
    if (major === PYTHON_TARGET[0] && minor === PYTHON_TARGET[1]) return { exe, version, exact: true };
  }
  for (const exe of await pythonCandidates()) {
    const version = await pythonVersion(exe);
    if (version) return { exe, version, exact: false };
  }
  return null;
}

async function longPathsEnabled() {
  const result = await run('reg.exe', [
    'query',
    'HKLM\\System\\CurrentControlSet\\Control\\FileSystem',
    '/v',
    'LongPathsEnabled',
  ]);
  if (!result.ok) return false;
  return /LongPathsEnabled\s+REG_DWORD\s+0x1/i.test(result.stdout);
}

/**
 * Shorten a path for display: relative to the project when it lives inside it,
 * absolute otherwise. Keeps the in-repo model and venv_convert paths readable
 * without hiding where a third-party install actually sits.
 */
function displayPath(target) {
  const relative = path.relative(paths.home(), target);
  return relative && !relative.startsWith('..') && !path.isAbsolute(relative) ? relative : target;
}

/**
 * Name the reason a core-package import failed, for the step detail.
 *
 * A missing package is the common case, but on Windows a present-but-unloadable
 * openvino ("DLL load failed while importing _pyopenvino") is the one worth
 * reading.
 */
function importFailure(stderr) {
  const missing = (stderr.match(/No module named '([^']+)'/) || [])[1];
  if (missing) return `${missing} is not installed`;
  const last = stderr.split(/\r?\n/).filter((line) => line.trim()).pop();
  if (!last) return 'the core packages do not import';
  const text = last.trim();
  return text.length > 140 ? `${text.slice(0, 139)}…` : text;
}

function freeDiskGb(target) {
  try {
    const stat = fs.statfsSync(target);
    return gb(stat.bavail * stat.bsize);
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Shared actions
// ---------------------------------------------------------------------------

let activeChild = null;

/**
 * Run a child process, forwarding its output line by line. Resolves with the
 * exit code; codes outside `okCodes` reject, so callers that distinguish
 * failure modes can widen the set and inspect the code themselves.
 */
function stream(emit, file, args, options, okCodes = [0]) {
  return new Promise((resolve, reject) => {
    const child = spawn(file, args, {
      ...options,
      shell: false,
      windowsHide: true,
      env: { ...process.env, ...config.proxyEnv(), PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    activeChild = child;

    let tail = '';
    const onData = (chunk) => {
      const text = tail + chunk.toString('utf8').replace(/\r(?!\n)/g, '\n');
      const lines = text.split(/\r?\n/);
      tail = lines.pop() ?? '';
      for (const line of lines) if (line.trim()) emit(line);
    };
    child.stdout.on('data', onData);
    child.stderr.on('data', onData);

    child.on('error', (error) => {
      activeChild = null;
      reject(new Error(`${path.basename(file)} could not be started: ${error.message}`));
    });
    child.on('exit', (code, signal) => {
      activeChild = null;
      if (tail.trim()) emit(tail);
      if (signal) return reject(new Error(`Cancelled (${signal}).`));
      if (!okCodes.includes(code)) return reject(new Error(`${path.basename(file)} exited with code ${code}.`));
      resolve(code);
    });
  });
}

async function ensureVenv(emit, { dir, interpreter, cwd }) {
  if (fs.existsSync(dir) && !fs.existsSync(paths.venvPython(dir))) {
    emit(`Removing incomplete environment at ${dir}`);
    fs.rmSync(dir, { recursive: true, force: true });
  }
  if (fs.existsSync(paths.venvPython(dir))) {
    emit('Environment already exists.');
    return;
  }
  emit(`Creating virtual environment with ${interpreter}`);
  await stream(emit, interpreter, ['-m', 'venv', dir], { cwd });
}

async function installRequirements(emit, { dir, requirements, cwd, upgrade = false }) {
  const python = paths.venvPython(dir);
  if (!fs.existsSync(python)) throw new Error('Create the environment first.');
  emit('Upgrading pip…');
  await stream(emit, python, ['-m', 'pip', 'install', '--upgrade', 'pip', '--no-input'], { cwd });
  emit(`Installing ${path.basename(requirements)}${upgrade ? ' (upgrading)' : ''} — this takes a while…`);
  const args = ['-m', 'pip', 'install', ...(upgrade ? ['--upgrade'] : []), '-r', requirements, '--no-input'];
  await stream(emit, python, args, { cwd });
}

/**
 * Create / Upgrade / Recreate for one virtual environment. Every option is a
 * zero-arg function because SMART_CLASSROOM_HOME can change at runtime.
 */
function venvActions({ dir, requirements, cwd, interpreter }) {
  const target = async () => ({ dir: dir(), requirements: requirements(), cwd: cwd(), interpreter: await interpreter() });

  return [
    {
      id: 'create',
      label: 'Create',
      requiresBackendStopped: true,
      async run(emit) {
        const options = await target();
        await ensureVenv(emit, options);
        await installRequirements(emit, options);
      },
    },
    {
      id: 'upgrade',
      label: 'Upgrade',
      requiresBackendStopped: true,
      visible: () => fs.existsSync(paths.venvPython(dir())),
      async run(emit) {
        await installRequirements(emit, { ...(await target()), upgrade: true });
      },
    },
    {
      id: 'recreate',
      label: 'Recreate',
      destructive: true,
      requiresBackendStopped: true,
      visible: () => fs.existsSync(dir()),
      async run(emit) {
        const options = await target();
        if (fs.existsSync(options.dir)) {
          emit(`Deleting ${options.dir}`);
          fs.rmSync(options.dir, { recursive: true, force: true });
        }
        await ensureVenv(emit, options);
        await installRequirements(emit, options);
      },
    },
  ];
}

async function wingetInstall(emit, id, label) {
  const winget = await run('where.exe', ['winget']);
  if (!winget.ok) throw new Error(`winget is not available; install ${label} manually.`);
  await stream(
    emit,
    'winget.exe',
    ['install', '-e', '--id', id, '--source', 'winget', '--accept-source-agreements', '--accept-package-agreements'],
    { cwd: paths.home() }
  );
}

// ---------------------------------------------------------------------------
// Steps
// ---------------------------------------------------------------------------

const STEPS = [
  {
    id: 'os',
    label: 'Operating system',
    section: 'system',
    async check() {
      const build = Number(os.release().split('.')[2] || 0);
      if (process.platform !== 'win32') return { status: STATUS.FAILED, detail: `${process.platform} is not supported` };
      // Windows 11 reports build 22000 or higher.
      return build >= 22000
        ? { status: STATUS.OK, detail: `Windows 11 (build ${build})` }
        : { status: STATUS.WARN, detail: `Windows build ${build}; Windows 11 is recommended` };
    },
  },
  {
    id: 'cpu',
    label: 'Processor',
    section: 'system',
    async check() {
      const model = (os.cpus()[0]?.model ?? '').trim();
      return /Intel.*Core.*Ultra/i.test(model)
        ? { status: STATUS.OK, detail: model }
        : { status: STATUS.WARN, detail: `${model || 'Unknown'}; Intel Core Ultra is recommended` };
    },
  },
  {
    id: 'memory',
    label: 'System memory',
    section: 'system',
    async check() {
      const total = gb(os.totalmem());
      return total >= MIN_RAM_GB * RAM_TOLERANCE
        ? { status: STATUS.OK, detail: `${total} GB` }
        : { status: STATUS.WARN, detail: `${total} GB; ${MIN_RAM_GB} GB recommended` };
    },
  },
  {
    id: 'disk',
    label: 'Free disk space',
    section: 'system',
    async check() {
      const free = freeDiskGb(paths.home());
      if (free === null) return { status: STATUS.UNKNOWN, detail: 'Could not determine free space' };
      return free >= MIN_DISK_GB
        ? { status: STATUS.OK, detail: `${free} GB free` }
        : { status: STATUS.WARN, detail: `${free} GB free; ${MIN_DISK_GB} GB recommended` };
    },
  },
  {
    id: 'gpu',
    label: 'Intel GPU',
    section: 'system',
    async check() {
      const device = await pnputilDevice('Display', /Intel\(R\)[^\r\n]*?(Arc|Iris|UHD|Graphics|GPU)[^\r\n]*/i);
      if (!device) {
        return { status: STATUS.WARN, detail: 'No Intel GPU detected' };
      }
      return describeDriver(device.name, await driverVersionFor(device.inf), LATEST_GPU_DRIVER);
    },
  },
  {
    id: 'npu',
    label: 'Intel NPU',
    section: 'system',
    async check() {
      const device = await pnputilDevice('ComputeAccelerator', /Intel\(R\)[^\r\n]*?(AI Boost|NPU|Neural)[^\r\n]*/i);
      if (!device) {
        return { status: STATUS.WARN, detail: 'No Intel NPU detected', hint: NPU_DRIVER_URL };
      }
      const result = describeDriver(device.name, await driverVersionFor(device.inf), LATEST_NPU_DRIVER);
      if (result.status === STATUS.WARN) result.hint = NPU_DRIVER_URL;
      return result;
    },
  },
  {
    id: 'longPaths',
    label: 'Windows long paths',
    section: 'system',
    async check() {
      return (await longPathsEnabled())
        ? { status: STATUS.OK, detail: 'Enabled' }
        : {
            status: STATUS.MISSING,
            detail: 'Disabled; model downloads with deep paths can fail',
            hint: 'Requires an administrator prompt',
          };
    },
    actions: [
      {
        id: 'enable',
        label: 'Enable',
        async run(emit) {
          emit('Requesting administrator privileges…');
          const command =
            "Start-Process -FilePath reg.exe -Verb RunAs -Wait -ArgumentList 'add','HKLM\\System\\CurrentControlSet\\Control\\FileSystem','/v','LongPathsEnabled','/t','REG_DWORD','/d','1','/f'";
          await stream(emit, 'powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', command], {
            cwd: paths.home(),
          });
          if (!(await longPathsEnabled())) {
            throw new Error('Long paths are still disabled; the prompt may have been declined.');
          }
        },
      },
    ],
  },

  {
    id: 'python',
    label: 'Python 3.12',
    section: 'software',
    async check() {
      const found = await findPython();
      if (!found) {
        return {
          status: STATUS.MISSING,
          detail: 'No interpreter found; needed to create the Python environment',
          hint: 'winget install -e --id Python.Python.3.12 --source winget',
        };
      }
      return found.exact
        ? { status: STATUS.OK, detail: `${found.version} (${found.exe})` }
        : {
            status: STATUS.WARN,
            detail: `${found.version} (${found.exe}); 3.12.x is the verified version, others may fail to build the environment`,
            hint: 'winget install -e --id Python.Python.3.12 --source winget',
          };
    },
    actions: [
      {
        id: 'install',
        label: 'Install',
        async run(emit) {
          await wingetInstall(emit, 'Python.Python.3.12', 'Python 3.12');
          emit('Installed.');
        },
      },
    ],
  },
  {
    id: 'node',
    label: 'Node.js',
    section: 'software',
    async check() {
      return { status: STATUS.OK, detail: `${process.versions.node} (bundled with this app; nothing to install)` };
    },
  },
  {
    id: 'ffmpeg',
    label: 'FFmpeg',
    section: 'software',
    async check() {
      const result = await run('where.exe', ['ffmpeg']);
      if (!result.ok) {
        return {
          status: STATUS.MISSING,
          detail: 'Not found on PATH; audio extraction and video pipelines need it',
          hint: 'winget install -e --id Gyan.FFmpeg --source winget',
        };
      }
      const exe = result.stdout.split(/\r?\n/)[0].trim();
      const version = await run(exe, ['-version']);
      // The banner reads "ffmpeg version <build> Copyright (c) …"; keep the build.
      const banner = version.stdout.split(/\r?\n/)[0] ?? '';
      const build = (banner.match(/^ffmpeg version (\S+)/i) || [])[1];
      // Which ffmpeg matters: a second copy earlier on PATH is a common surprise.
      return { status: STATUS.OK, detail: build ? `${build} (${exe})` : banner || exe };
    },
    actions: [{ id: 'install', label: 'Install', run: (emit) => wingetInstall(emit, 'Gyan.FFmpeg', 'FFmpeg') }],
  },
  {
    id: 'dlStreamer',
    label: 'DL Streamer',
    section: 'software',
    async check() {
      // Its installer records both values under this key.
      const install = await winEnv.dlStreamerInstall();
      if (!install) {
        return {
          status: STATUS.MISSING,
          detail: `Not installed; video analytics pipelines cannot run without it`,
          hint: DLSTREAMER_URL,
        };
      }
      // Check installDir
      if (!install.installDir || !fs.existsSync(install.installDir)) {
        return {
          status: STATUS.MISSING,
          detail: install.version
            ? `${install.version} is registered but its files are missing; reinstall to run video pipelines`
            : 'Registered but its files are missing; reinstall to run video pipelines',
          hint: DLSTREAMER_URL,
        };
      }
      const { version, installDir } = install;
      if (!version) {
        return { status: STATUS.WARN, detail: `Version unknown (${installDir})`, hint: DLSTREAMER_URL };
      }

      return compareVersions(version, REQUIRED_DLSTREAMER) >= 0
        ? { status: STATUS.OK, detail: `${version} (${installDir})` }
        : {
            status: STATUS.WARN,
            detail: `${version} (${installDir}); ${REQUIRED_DLSTREAMER} is required for video pipelines`,
            hint: DLSTREAMER_URL,
          };
    },
    // Downloading and running the installer is the same job the setup script
    // does, so drive its script rather than duplicating the logic here.
    actions: [
      {
        id: 'install',
        label: 'Install',
        async run(emit) {
          const script = paths.dlStreamerScript();
          if (!fs.existsSync(script)) throw new Error(`${script} is missing.`);

          const { httpProxy, httpsProxy } = config.readProxyConfig();
          emit('Downloading and running the DL Streamer installer — accept the administrator prompt when it appears…');
          // -Yes answers the script's own confirmations, which cannot be
          // reached here: the child has no stdin.
          const code = await stream(
            emit,
            'powershell.exe',
            [
              '-NoProfile',
              '-NonInteractive',
              '-ExecutionPolicy',
              'Bypass',
              '-File',
              script,
              '-Install',
              '-Yes',
              '-RequiredVersion',
              REQUIRED_DLSTREAMER,
              ...(httpProxy ? ['-HttpProxy', httpProxy] : []),
              ...(httpsProxy ? ['-HttpsProxy', httpsProxy] : []),
            ],
            { cwd: paths.home() },
            [0, 1, 2]
          );
          if (code === 1) {
            throw new Error(`The upgrade to DL Streamer ${REQUIRED_DLSTREAMER} failed; install it from ${DLSTREAMER_URL}`);
          }
          if (code === 2) {
            throw new Error(`DL Streamer was not installed; install it from ${DLSTREAMER_URL}`);
          }
        },
      },
    ],
  },
  {
    id: 'venv',
    label: 'Python environment',
    section: 'software',
    // Built with the interpreter the Python step finds.
    requires: ['python'],
    async check() {
      const dir = paths.venvDir();
      const exe = paths.venvPython();
      if (!fs.existsSync(exe)) {
        return {
          status: STATUS.MISSING,
          detail: `Not created; the backend cannot start until it exists (${dir})`,
        };
      }

      const version = await pythonVersion(exe);
      if (!version) return { status: STATUS.FAILED, detail: `Its interpreter does not run; select Recreate (${dir})` };

      const imports = await run(exe, ['-c', 'import fastapi, uvicorn, openvino; print("ok")'], 60000);
      return imports.ok
        ? { status: STATUS.OK, detail: `Python ${version} with the core packages (${dir})` }
        : {
            status: STATUS.MISSING,
            detail: `Python ${version}; ${importFailure(imports.stderr)} — select Create to install the requirements`,
          };
    },
    actions: venvActions({
      dir: () => paths.venvDir(),
      requirements: () => paths.requirementsFile(),
      cwd: () => paths.home(),
      interpreter: async () => {
        const found = await findPython();
        if (!found) throw new Error('No Python interpreter found; install Python 3.12 first.');
        return found.exe;
      },
    }),
  },
  {
    id: 'gradingVenv',
    label: 'Grading conversion environment',
    section: 'software',
    // Created from the backend venv's interpreter.
    requires: ['venv'],
    optional: true,
    enabled: () => config.featureEnabled('grading'),
    async check() {
      const dir = paths.convertVenvDir();
      if (!fs.existsSync(paths.venvPython(dir))) {
        return { status: STATUS.MISSING, detail: 'Not created; needed once to convert the layout detection model' };
      }
      // paddle2onnx is what the conversion actually shells out to.
      const tool = path.join(dir, paths.isWindows ? 'Scripts\\paddle2onnx.exe' : 'bin/paddle2onnx');
      return fs.existsSync(tool)
        ? { status: STATUS.OK, detail: `paddle2onnx ready (${displayPath(dir)})` }
        : { status: STATUS.MISSING, detail: 'Created, but paddle2onnx is missing; select Create to install it' };
    },
    // paddle2onnx conflicts with the main environment, hence the separate venv.
    actions: venvActions({
      dir: () => paths.convertVenvDir(),
      requirements: () => paths.convertRequirementsFile(),
      cwd: () => paths.layoutServiceDir(),
      interpreter: async () => {
        const base = paths.venvPython();
        if (!fs.existsSync(base)) throw new Error('Create the Python environment first.');
        return base;
      },
    }),
  },
  {
    id: 'layoutModel',
    label: 'Layout detection model',
    section: 'software',
    // ensure_layout_model.py runs on the backend venv's interpreter.
    requires: ['venv'],
    optional: true,
    enabled: () => config.featureEnabled('grading'),
    async check() {
      return fs.existsSync(paths.layoutIrModel())
        ? { status: STATUS.OK, detail: `OpenVINO IR ready (${displayPath(path.dirname(paths.layoutIrModel()))})` }
        : {
            status: STATUS.MISSING,
            detail: 'Not prepared; grading needs it. Preparing downloads and converts the model.',
          };
    },
    actions: [
      {
        id: 'prepare',
        label: 'Prepare',
        async run(emit) {
          const python = paths.venvPython();
          if (!fs.existsSync(python)) throw new Error('Create the Python environment first.');
          emit('Downloading and converting the layout model (several minutes)…');
          await stream(emit, python, ['ensure_layout_model.py'], { cwd: paths.layoutServiceDir() });
          if (!fs.existsSync(paths.layoutIrModel())) {
            throw new Error('Conversion finished but no IR model was produced.');
          }
        },
      },
    ],
  },
];

const BY_ID = new Map(STEPS.map((step) => [step.id, step]));

// ---------------------------------------------------------------------------
// Runner
// ---------------------------------------------------------------------------

class SetupRunner extends EventEmitter {
  constructor(logs) {
    super();
    this.logs = logs;
    this.state = new Map();
    this.busy = false;
    for (const step of STEPS) {
      this.state.set(step.id, { status: STATUS.UNKNOWN, detail: '', hint: null });
    }
  }

  snapshot() {
    return STEPS.filter((step) => (step.enabled ? step.enabled() : true)).map((step) => {
      const state = this.state.get(step.id);
      return {
        id: step.id,
        label: step.label,
        section: step.section,
        optional: !!step.optional,
        // Steps this one cannot run without, so the screen can say so instead of
        // letting the user click into a guaranteed failure.
        requires: step.requires ?? [],
        actions: (step.actions ?? [])
          .filter((action) => (action.visible ?? visibleUnlessOk)(state.status))
          .map((action) => ({
            id: action.id,
            label: action.label,
            destructive: !!action.destructive,
          })),
        ...state,
      };
    });
  }

  sections() {
    return SECTIONS;
  }

  emitChanged() {
    this.emit('changed', this.snapshot());
  }

  log(line) {
    this.logs.note(LOG_ID, line);
  }

  /**
   * Re-read PATH and the DL Streamer variables from the registry.
   *
   * Every check here shells out through the inherited environment, so without
   * this an install performed in this session stays undetected until the app is
   * restarted — the tool is on the registry PATH, but not on ours.
   */
  async refreshEnvironment() {
    try {
      const added = await winEnv.refreshPath();
      if (added.length) this.log(`PATH refreshed from the registry: ${added.join(', ')}`);
      const dls = await winEnv.applyDlStreamerEnv();
      if (dls) this.log(`DL Streamer environment applied from ${dls.installDir}`);
    } catch (error) {
      // Detection still runs with the environment we already have.
      this.log(`Could not refresh the environment: ${error.message}`);
    }
  }

  /** Re-run every detection. Never installs anything. */
  async checkAll() {
    // Picks up anything installed since this process started, including by an
    // installer run outside the app.
    await this.refreshEnvironment();

    for (const step of STEPS) {
      if (step.enabled && !step.enabled()) continue;
      this.state.set(step.id, { ...this.state.get(step.id), status: STATUS.RUNNING });
      this.emitChanged();
      try {
        const result = await step.check();
        this.state.set(step.id, { status: result.status, detail: result.detail, hint: result.hint ?? null });
      } catch (error) {
        this.state.set(step.id, { status: STATUS.FAILED, detail: error.message, hint: null });
      }
      this.emitChanged();
    }
    return this.snapshot();
  }

  find(stepId, actionId) {
    const step = BY_ID.get(stepId);
    if (!step) throw new Error(`Unknown setup step: ${String(stepId).slice(0, 64)}`);
    const action = (step.actions ?? []).find((entry) => entry.id === actionId);
    if (!action) throw new Error(`${step.label} has no action "${String(actionId).slice(0, 64)}".`);
    return { step, action };
  }

  async runStep(stepId, actionId) {
    const { step, action } = this.find(stepId, actionId);
    if (this.busy) throw new Error('Another setup step is already running.');

    // Windows locks the .pyd/.dll files of a running interpreter, so pip would
    // fail part-way through and leave the environment half-upgraded.
    if (action.requiresBackendStopped) {
      const port = registry.get('backend')?.port;
      if (port && !(await proc.isPortFree(port))) {
        throw new Error('Stop the backend first: its Python environment is in use.');
      }
    }

    this.busy = true;
    this.logs.openSink(LOG_ID);
    this.state.set(step.id, { status: STATUS.RUNNING, detail: `${action.label}…`, hint: null });
    this.emitChanged();

    const emit = (line) => this.log(line);
    try {
      this.log(`=== ${step.label}: ${action.label} ===`);
      await action.run(emit);
      // An install just changed the registry PATH; the verifying check below
      // shells out and would otherwise still be looking at the old one.
      await this.refreshEnvironment();
      const result = await step.check();
      this.state.set(step.id, { status: result.status, detail: result.detail, hint: result.hint ?? null });
      this.log(`=== ${step.label}: ${result.status} ===`);
    } catch (error) {
      this.state.set(step.id, { status: STATUS.FAILED, detail: error.message, hint: null });
      this.log(`=== ${step.label} failed: ${error.message} ===`);
      throw error;
    } finally {
      this.busy = false;
      this.emitChanged();
    }
    return this.state.get(step.id);
  }

  cancel() {
    if (!activeChild) return false;
    activeChild.kill();
    this.log('Cancellation requested.');
    return true;
  }
}

module.exports = { SetupRunner, STATUS, SECTIONS, LOG_ID };
