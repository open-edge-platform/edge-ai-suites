// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Supervisor for the Smart Classroom process tree.
//
// Only `managed` services are spawned here (today: the backend). Everything the
// backend starts in turn is observed by health probe and taken down with it via
// a tree kill plus a port sweep scoped to the registry.

const fs = require('fs');
const net = require('net');
const { spawn } = require('child_process');
const { EventEmitter } = require('events');

const registry = require('./registry.cjs');
const config = require('./config-store.cjs');
const proc = require('./win-proc.cjs');

const HEALTH_INTERVAL_MS = 2000;
const HEALTH_TIMEOUT_MS = 3000;
// Model loading makes a cold backend slow to answer; matches the grace period
// the PowerShell startup script used before declaring a crash.
const START_GRACE_MS = 60000;
const UNHEALTHY_STRIKES = 3;
const STOP_TIMEOUT_MS = 20000;
// After a kill, a detached child that was still booting can take a moment to
// bind its port. Wait out that window before calling the tree down, or the
// respawn races an orphan of the run we just stopped.
const PORT_SETTLE_MS = 1500;
const PORT_SWEEP_ROUNDS = 3;

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const STATUS = {
  STOPPED: 'stopped',
  STARTING: 'starting',
  HEALTHY: 'healthy',
  DEGRADED: 'degraded',
  STOPPING: 'stopping',
  FAILED: 'failed',
};

async function probeHttp(url, timeoutMs) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
    return response.ok;
  } catch {
    return false;
  }
}

function probeTcp(port, timeoutMs) {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host: '127.0.0.1' });
    const done = (up) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(up);
    };
    socket.setTimeout(timeoutMs);
    socket.once('connect', () => done(true));
    socket.once('timeout', () => done(false));
    socket.once('error', () => done(false));
  });
}

function probe(service) {
  const timeoutMs = service.healthTimeoutMs || HEALTH_TIMEOUT_MS;
  if (service.healthUrl) return probeHttp(service.healthUrl, timeoutMs);
  if (service.port) return probeTcp(service.port, timeoutMs);
  return Promise.resolve(false);
}

class ServiceManager extends EventEmitter {
  constructor(logs) {
    super();
    this.logs = logs;
    this.logs.setRoute(registry.routeLogLine);
    this.children = new Map(); // id -> ChildProcess
    this.state = new Map();
    this.timer = null;
    this.ticking = false;

    for (const service of registry.SERVICES) {
      this.state.set(service.id, {
        status: STATUS.STOPPED,
        pid: null,
        external: false,
        startedAt: null,
        healthySince: null,
        exitCode: null,
        error: null,
        strikes: 0,
      });
    }
  }

  start() {
    if (this.timer) return;
    this.timer = setInterval(() => this.tick(), HEALTH_INTERVAL_MS);
    this.tick();
  }

  stopPolling() {
    clearInterval(this.timer);
    this.timer = null;
  }

  snapshot() {
    return registry.SERVICES.map((service) => {
      const state = this.state.get(service.id);
      return {
        ...registry.describe(service),
        status: state.status,
        pid: state.pid,
        external: state.external,
        // Managed services need their interpreter on disk before Start means
        // anything; the UI uses this to point a first-time user at Setup.
        runnable: service.managed ? fs.existsSync(registry.resolveCommand(service).command) : true,
        startedAt: state.startedAt,
        uptimeMs: state.healthySince ? Date.now() - state.healthySince : null,
        exitCode: state.exitCode,
        error: state.error,
        logFile: this.logs.logFile(service.id),
      };
    });
  }

  emitChanged() {
    this.emit('changed', this.snapshot());
  }

  setStatus(id, status, patch = {}) {
    const state = this.state.get(id);
    const next = { ...state, status, ...patch };
    if (status === STATUS.HEALTHY && state.status !== STATUS.HEALTHY) next.healthySince = Date.now();
    if (status !== STATUS.HEALTHY) next.healthySince = null;
    const changed = Object.keys(next).some((key) => next[key] !== state[key]);
    this.state.set(id, next);
    return changed;
  }

  // ---------------------------------------------------------------------
  // Health reconciliation
  // ---------------------------------------------------------------------
  async tick() {
    if (this.ticking) return;
    this.ticking = true;
    try {
      const enabled = registry.SERVICES.filter((service) => service.enabled());
      const probes = await Promise.all(enabled.map((service) => probe(service)));
      const up = new Map(enabled.map((service, index) => [service.id, probes[index]]));

      // Children are spawned by the backend, not by us, so their pids can only
      // come from whoever is holding the port.
      const livePorts = enabled.filter((service) => up.get(service.id) && service.port).map((service) => service.port);
      const portPids = livePorts.length ? await proc.pidsForPorts(livePorts) : new Map();

      let changed = false;
      for (const service of registry.SERVICES) {
        if (!service.enabled()) {
          changed = this.setStatus(service.id, STATUS.STOPPED, { strikes: 0, pid: null }) || changed;
          continue;
        }
        changed =
          (service.managed
            ? this.reconcileManaged(service, up, portPids)
            : this.reconcileObserved(service, up, portPids)) || changed;
      }
      if (changed) this.emitChanged();
    } finally {
      this.ticking = false;
    }
  }

  reconcileManaged(service, up, portPids) {
    const state = this.state.get(service.id);
    if (state.status === STATUS.STOPPING) return false;

    const child = this.children.get(service.id);
    const healthy = up.get(service.id);

    if (healthy) {
      return this.setStatus(service.id, STATUS.HEALTHY, {
        strikes: 0,
        error: null,
        exitCode: null,
        // A healthy port with no child of ours means the legacy PowerShell path
        // (or a previous run) owns it; attach rather than fight over it.
        external: !child,
        pid: child ? child.pid : portPids.get(service.port) ?? null,
      });
    }

    if (!child) return false;

    if (state.status === STATUS.STARTING && Date.now() - state.startedAt < START_GRACE_MS) return false;

    const strikes = state.strikes + 1;
    if (strikes < UNHEALTHY_STRIKES) return this.setStatus(service.id, state.status, { strikes });
    return this.setStatus(service.id, STATUS.DEGRADED, { strikes });
  }

  reconcileObserved(service, up, portPids) {
    if (up.get(service.id)) {
      return this.setStatus(service.id, STATUS.HEALTHY, {
        strikes: 0,
        error: null,
        pid: portPids.get(service.port) ?? null,
      });
    }

    const owner = this.state.get(service.ownedBy);
    // Only claim "starting" while an owner we launched is still inside its boot
    // window; for an attached (external) owner we have no start time to trust.
    const ownerStarting =
      owner &&
      (owner.status === STATUS.STARTING ||
        (owner.status === STATUS.HEALTHY && !owner.external && Date.now() - owner.healthySince < START_GRACE_MS));
    return this.setStatus(service.id, ownerStarting ? STATUS.STARTING : STATUS.STOPPED, { strikes: 0, pid: null });
  }

  // ---------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------
  /**
   * @param {{adopt?: boolean}} options `adopt` attaches to an already-healthy
   *   port instead of starting anything. True for a plain Start (the legacy
   *   PowerShell path may own it); false for a restart, where a live port can
   *   only be an orphan of the run we just stopped.
   */
  async startService(id, { adopt = true } = {}) {
    const service = registry.get(id);
    if (!service) throw new Error(`Unknown service: ${id}`);
    if (!service.managed) throw new Error(`${service.label} is started by ${service.ownedBy}, not directly.`);
    if (!service.enabled()) throw new Error(`${service.label} is disabled in config.yaml.`);
    if (this.children.has(id)) return { started: false, reason: 'already-running' };

    if (adopt && (await probe(service))) {
      this.setStatus(id, STATUS.HEALTHY, { external: true, pid: null, error: null });
      this.emitChanged();
      return { started: false, reason: 'already-healthy' };
    }

    const { command, args, cwd, display } = registry.resolveCommand(service);
    if (!fs.existsSync(command)) {
      const error = `Python interpreter not found at ${command}. Run setup to create the virtual environment.`;
      this.setStatus(id, STATUS.FAILED, { error });
      this.emitChanged();
      throw new Error(error);
    }

    // Children are logged through this process, so a fresh run starts from a
    // clean buffer for the whole tree.
    for (const other of registry.SERVICES) this.logs.clear(other.id);
    this.logs.openSink(id);

    // start_services.py detaches its children, so a crashed or force-killed
    // manager leaves them holding ports. The service itself is not healthy at
    // this point, so anything still listening is an orphan of a previous run.
    const orphans = await proc.killPorts(registry.ownedPorts(id));
    for (const { port, pid } of orphans) {
      this.logs.note(id, `Reclaimed port ${port} from orphaned process ${pid}`);
    }
    if (orphans.length) await proc.waitForPortsFree(registry.ownedPorts(id), 10000);

    this.logs.note(id, `Starting: ${display} (cwd ${cwd})`);

    const child = spawn(command, args, {
      cwd,
      env: {
        ...process.env,
        ...config.proxyEnv(),
        PYTHONUNBUFFERED: '1',
        PYTHONIOENCODING: 'utf-8',
      },
      shell: false,
      windowsHide: true,
      detached: !proc.isWindows,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    this.children.set(id, child);
    this.setStatus(id, STATUS.STARTING, {
      pid: child.pid,
      external: false,
      startedAt: Date.now(),
      exitCode: null,
      error: null,
      strikes: 0,
    });
    this.emitChanged();

    child.stdout.on('data', (chunk) => this.logs.write(id, chunk, 'stdout'));
    child.stderr.on('data', (chunk) => this.logs.write(id, chunk, 'stderr'));

    child.on('error', (error) => {
      this.children.delete(id);
      this.logs.note(id, `Failed to start: ${error.message}`);
      this.setStatus(id, STATUS.FAILED, { pid: null, error: error.message });
      this.emitChanged();
    });

    child.on('exit', (code, signal) => {
      this.children.delete(id);
      const state = this.state.get(id);
      this.logs.note(id, `Process exited (code ${code}, signal ${signal ?? 'none'})`);
      this.logs.closeSink(id);
      if (state.status === STATUS.STOPPING) return;
      this.setStatus(id, STATUS.FAILED, {
        pid: null,
        exitCode: code,
        error: `Exited with code ${code}${signal ? ` (${signal})` : ''}. See logs.`,
      });
      this.emitChanged();
    });

    return { started: true, pid: child.pid };
  }

  async stopService(id) {
    const service = registry.get(id);
    if (!service) throw new Error(`Unknown service: ${id}`);
    if (!service.managed) throw new Error(`${service.label} stops with ${service.ownedBy}.`);

    // Stopping mid-launch is the dangerous case: the tree has already spawned
    // children that have not bound their ports yet. Read it before STOPPING
    // overwrites it.
    const launching = this.state.get(id).status === STATUS.STARTING;

    this.setStatus(id, STATUS.STOPPING);
    this.emitChanged();

    const ports = registry.ownedPorts(id);
    const child = this.children.get(id);

    if (child) {
      this.logs.note(id, `Stopping process tree (pid ${child.pid})…`);
      const exited = new Promise((resolve) => child.once('exit', resolve));
      await proc.killTree(child.pid);
      await Promise.race([exited, delay(STOP_TIMEOUT_MS)]);
      this.children.delete(id);
    }

    const held = await this.sweepOwnedPorts(id, ports, launching);
    this.logs.closeSink(id);

    // Reporting "stopped" while an orphan still owns a port is what makes a
    // restart look like it did nothing: the respawned tree cannot take the port
    // back, and the health probe then reports the orphan as healthy.
    if (held.length) {
      const error = `${service.label} stopped, but ${held.join(', ')} ${
        held.length > 1 ? 'are' : 'is'
      } still in use. Close whatever is holding ${held.length > 1 ? 'them' : 'it'} and try again.`;
      this.setStatus(id, STATUS.FAILED, { pid: null, external: false, startedAt: null, error, strikes: 0 });
      this.emitChanged();
      throw new Error(error);
    }

    this.setStatus(id, STATUS.STOPPED, { pid: null, external: false, startedAt: null, error: null, strikes: 0 });
    this.emitChanged();
    return { stopped: true, ports };
  }

  /**
   * Free every port the service owns, and prove it stayed free.
   *
   * Children the backend spawned outlive the tree kill (start_services.py
   * detaches them), and one that was still booting binds its port *after* a
   * single sweep has already found it free. So each round kills what is there,
   * waits, then pauses long enough for a late binder to show up. Returns the
   * ports still held once the rounds run out.
   */
  async sweepOwnedPorts(id, ports, launching) {
    const stillHeld = async () => {
      const held = [];
      for (const port of ports) if (!(await proc.isPortFree(port))) held.push(port);
      return held;
    };

    for (let round = 1; round <= PORT_SWEEP_ROUNDS; round += 1) {
      const killed = await proc.killPorts(ports);
      for (const { port, pid } of killed) this.logs.note(id, `Killed leftover process ${pid} on port ${port}`);
      await proc.waitForPortsFree(ports, STOP_TIMEOUT_MS);

      // Nothing was lingering and nothing was mid-launch: no late binder to wait for.
      if (!killed.length && !launching) return [];

      await delay(PORT_SETTLE_MS);
      const held = await stillHeld();
      if (!held.length) return [];
      this.logs.note(id, `Port ${held.join(', ')} taken again after sweep ${round}; sweeping once more.`);
    }

    return stillHeld();
  }

  async restartService(id) {
    await this.stopService(id);
    // adopt: false — stopService just proved these ports were free, so anything
    // answering now is an orphan of the run we stopped, not a backend someone
    // else started. Attaching to it would strand the restart.
    return this.startService(id, { adopt: false });
  }

  // Called on app quit: only tear down what this process actually started.
  async shutdown() {
    this.stopPolling();
    for (const service of registry.SERVICES) {
      if (service.managed && this.children.has(service.id)) {
        try {
          await this.stopService(service.id);
        } catch {
          // Best effort during quit.
        }
      }
    }
  }
}

module.exports = { ServiceManager, STATUS };
