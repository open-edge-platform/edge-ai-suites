// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Process/port helpers built on plain Win32 executables (netstat, taskkill).

const net = require('net');
const { execFile } = require('child_process');

const isWindows = process.platform === 'win32';

function run(file, args, timeout = 10000) {
  return new Promise((resolve) => {
    execFile(file, args, { timeout, windowsHide: true }, (error, stdout, stderr) => {
      resolve({ ok: !error, stdout: stdout || '', stderr: stderr || '' });
    });
  });
}

// PIDs listening on `port`. Empty when the port is free or the lookup failed.
async function listenersOnPort(port) {
  if (!Number.isInteger(port)) return [];

  if (isWindows) {
    const { ok, stdout } = await run('netstat.exe', ['-ano', '-p', 'TCP']);
    if (!ok) return [];
    return [...parseNetstat(stdout, [port]).get(port) ?? []];
  }

  const { ok, stdout } = await run('lsof', ['-nP', `-iTCP:${port}`, '-sTCP:LISTEN', '-t']);
  if (!ok) return [];
  return stdout
    .split(/\s+/)
    .map(Number)
    .filter((pid) => Number.isInteger(pid) && pid > 0);
}

function parseNetstat(stdout, ports) {
  const wanted = new Set(ports);
  const result = new Map();
  for (const line of stdout.split(/\r?\n/)) {
    if (!line.includes('LISTENING')) continue;
    const columns = line.trim().split(/\s+/);
    const local = columns[1] || '';
    const port = Number(local.slice(local.lastIndexOf(':') + 1));
    const pid = Number(columns[columns.length - 1]);
    if (!wanted.has(port) || !Number.isInteger(pid) || pid <= 0) continue;
    if (!result.has(port)) result.set(port, new Set());
    result.get(port).add(pid);
  }
  return result;
}

// One lookup for many ports; used by the health loop, which would otherwise
// spawn a netstat per service per tick. Returns port -> first listening pid.
async function pidsForPorts(ports) {
  const map = new Map();
  if (!ports.length) return map;

  if (isWindows) {
    const { ok, stdout } = await run('netstat.exe', ['-ano', '-p', 'TCP']);
    if (!ok) return map;
    for (const [port, pids] of parseNetstat(stdout, ports)) map.set(port, [...pids][0]);
    return map;
  }

  for (const port of ports) {
    const [pid] = await listenersOnPort(port);
    if (pid) map.set(port, pid);
  }
  return map;
}

function isAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error.code === 'EPERM';
  }
}

// Kill a process and its descendants.
async function killTree(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  if (isWindows) {
    const { ok } = await run('taskkill.exe', ['/PID', String(pid), '/T', '/F']);
    return ok;
  }
  try {
    process.kill(-pid, 'SIGKILL');
    return true;
  } catch {
    try {
      process.kill(pid, 'SIGKILL');
      return true;
    } catch {
      return false;
    }
  }
}

// Scoped sweep: only kills whatever still holds the given ports. Never matches
// on process name, so unrelated python/node processes are left alone.
async function killPorts(ports) {
  const killed = [];
  for (const port of ports) {
    for (const pid of await listenersOnPort(port)) {
      if (await killTree(pid)) killed.push({ port, pid });
    }
  }
  return killed;
}

function isPortFree(port, timeoutMs = 1000) {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host: '127.0.0.1' });
    const done = (free) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(free);
    };
    socket.setTimeout(timeoutMs);
    socket.once('connect', () => done(false));
    socket.once('timeout', () => done(true));
    socket.once('error', () => done(true));
  });
}

async function waitForPortsFree(ports, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const results = await Promise.all(ports.map((port) => isPortFree(port)));
    if (results.every(Boolean)) return true;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

module.exports = {
  isWindows,
  listenersOnPort,
  pidsForPorts,
  isAlive,
  killTree,
  killPorts,
  isPortFree,
  waitForPortsFree,
};
