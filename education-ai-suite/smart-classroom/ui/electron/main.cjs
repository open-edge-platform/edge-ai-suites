// Electron main process for the Smart Classroom UI.
//
// This layer is purely additive: the same `vite build` output that serves the
// plain web app is loaded here. In dev we point at the running Vite server
// (which already proxies /api/v1); when packaged we serve `dist/` through the
// embedded static + proxy micro-server (server.cjs).
//
// The Python backends are expected to be started separately.

const path = require('path');
const { app, BrowserWindow, Menu, ipcMain, shell } = require('electron');
const { startServer } = require('./server.cjs');

// Height (px) of the custom title bar strip. Matches the TopPanel so the
// native Window Controls Overlay buttons align with the app header.
const TITLE_BAR_HEIGHT = 63;

// Build an explicit application menu (File / Edit / View / Window) using
// standard roles.
function buildAppMenu() {
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac ? [{ role: 'appMenu' }] : []),
    { role: 'fileMenu' },
    { role: 'editMenu' },
    { role: 'viewMenu' },
    { role: 'windowMenu' },
  ];
  return Menu.buildFromTemplate(template);
}

// Build a right-click context menu with basic text operations, tailored to the
// clicked element. Returns null when there is nothing useful to show. `params`
// is the object from the webContents 'context-menu' event.
function buildContextMenu(params) {
  const { editFlags, isEditable, selectionText } = params;
  const hasSelection = selectionText.trim().length > 0;
  const template = [];

  if (isEditable) {
    template.push(
      { role: 'undo', enabled: editFlags.canUndo },
      { role: 'redo', enabled: editFlags.canRedo },
      { type: 'separator' },
      { role: 'cut', enabled: editFlags.canCut },
      { role: 'copy', enabled: editFlags.canCopy },
      { role: 'paste', enabled: editFlags.canPaste },
      { type: 'separator' },
      { role: 'selectAll', enabled: editFlags.canSelectAll }
    );
  } else if (hasSelection) {
    template.push(
      { role: 'copy', enabled: editFlags.canCopy },
      { type: 'separator' },
      { role: 'selectAll', enabled: editFlags.canSelectAll }
    );
  }

  return template.length ? Menu.buildFromTemplate(template) : null;
}

// Vite dev server URL, set by the `electron:dev` script. Absent when packaged.
const DEV_SERVER_URL = process.env.ELECTRON_START_URL;

let mainWindow = null;
let serverHandle = null;

async function resolveStartUrl() {
  if (DEV_SERVER_URL) return DEV_SERVER_URL;
  // Resolve `dist/` relative to this file (ui/electron/main.cjs -> ui/dist).
  const distPath = path.join(__dirname, '..', 'dist');
  serverHandle = await startServer(distPath);
  return `http://127.0.0.1:${serverHandle.port}`;
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    show: false,
    title: 'Smart Classroom',
    titleBarStyle: 'hidden',
    ...(process.platform !== 'darwin'
      ? {
        titleBarOverlay: {
          color: '#0071c5',
          symbolColor: '#ffffff',
          height: TITLE_BAR_HEIGHT,
        },
      }
      : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  // Open http(s) links (e.g. external links) in the OS browser
  // rather than inside the app window.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  // Right-click context menu with basic text operations.
  mainWindow.webContents.on('context-menu', (_event, params) => {
    const menu = buildContextMenu(params);
    if (menu) menu.popup({ window: mainWindow });
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.maximize();
    mainWindow.show();
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  const startUrl = await resolveStartUrl();
  await mainWindow.loadURL(startUrl);
}

// Single-instance: focus the existing window instead of opening a second one.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    Menu.setApplicationMenu(buildAppMenu());

    // Open the native application menu as a popup, positioned under the
    // title-bar menu button (coordinates come from the renderer, in viewport
    // pixels which map to the frameless window's content area).
    ipcMain.on('menu:popup', (event, position) => {
      const menu = Menu.getApplicationMenu();
      if (!menu) return;
      const win = BrowserWindow.fromWebContents(event.sender);
      const opts = win ? { window: win } : {};
      if (position && Number.isFinite(position.x) && Number.isFinite(position.y)) {
        opts.x = Math.round(position.x);
        opts.y = Math.round(position.y);
      }
      menu.popup(opts);
    });

    createWindow();
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
}

app.on('window-all-closed', () => {
  if (serverHandle) serverHandle.close();
  if (process.platform !== 'darwin') app.quit();
});
