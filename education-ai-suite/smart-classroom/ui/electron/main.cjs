// Electron main process for the Smart Classroom UI.
//
// This layer is purely additive: the same `vite build` output that serves the
// plain web app is loaded here. In dev we point at the running Vite server
// (which already proxies /api/v1); when packaged we serve `dist/` through the
// embedded static + proxy micro-server (server.cjs).
//
// The Python backends are expected to be started separately.

const fs = require('fs');
const path = require('path');
const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require('electron');
const { startServer } = require('./server.cjs');

// Height (px) of the custom title bar strip. Matches the TopPanel so the
// native Window Controls Overlay buttons align with the app header.
const TITLE_BAR_HEIGHT = 63;

// The Window Controls Overlay strip is painted by OS, not by the page, so a
// DOM overlay cannot dim it. The renderer reports which surface is on top and we
// recolour the caption to match.
const TITLE_BAR_THEMES = {
  // App header.
  default: { color: '#0071c5', symbolColor: '#ffffff' },
  // Brand blue and white composited under 50% black.
  dimmed: { color: '#003862', symbolColor: '#7f7f7f' },
  // The report panel is a white sheet pinned to the right edge, full height, so
  // it sits directly under the caption buttons.
  light: { color: '#ffffff', symbolColor: '#5a6374' },
};

// ---------------------------------------------------------------------------
// Native-menu localization
// ---------------------------------------------------------------------------
// The native application menu and right-click context menu are rendered by the
// OS shell, not React, so react-i18next cannot reach them. We keep a small label
// table here (mirroring src/i18n) and rebuild the menus when the renderer reports
// a language change. Roles are preserved for native behavior/accelerators; only
// the `label` is translated. Unknown languages fall back to English.
const MENU_LABELS = {
  en: {
    file: 'File', edit: 'Edit', view: 'View', window: 'Window',
    quit: 'Quit', close: 'Close',
    undo: 'Undo', redo: 'Redo', cut: 'Cut', copy: 'Copy', paste: 'Paste', selectAll: 'Select All',
    reload: 'Reload', forceReload: 'Force Reload', toggleDevTools: 'Toggle Developer Tools',
    resetZoom: 'Actual Size', zoomIn: 'Zoom In', zoomOut: 'Zoom Out', togglefullscreen: 'Toggle Full Screen',
    minimize: 'Minimize', zoom: 'Zoom',
  },
  zh: {
    file: '文件', edit: '编辑', view: '视图', window: '窗口',
    quit: '退出', close: '关闭',
    undo: '撤销', redo: '重做', cut: '剪切', copy: '复制', paste: '粘贴', selectAll: '全选',
    reload: '重新加载', forceReload: '强制重新加载', toggleDevTools: '切换开发者工具',
    resetZoom: '实际大小', zoomIn: '放大', zoomOut: '缩小', togglefullscreen: '切换全屏',
    minimize: '最小化', zoom: '缩放',
  },
};

// Current native-menu language; updated via the 'menu:setLanguage' IPC channel.
let currentLanguage = 'en';

function menuLabels(lang) {
  return MENU_LABELS[lang] || MENU_LABELS.en;
}

// Build an explicit application menu (File / Edit / View / Window) with
// translated labels. Standard roles preserve native behavior and accelerators.
function buildAppMenu(lang = currentLanguage) {
  const L = menuLabels(lang);
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac ? [{ role: 'appMenu' }] : []),
    {
      label: L.file,
      submenu: [{ role: isMac ? 'close' : 'quit', label: isMac ? L.close : L.quit }],
    },
    {
      label: L.edit,
      submenu: [
        { role: 'undo', label: L.undo },
        { role: 'redo', label: L.redo },
        { type: 'separator' },
        { role: 'cut', label: L.cut },
        { role: 'copy', label: L.copy },
        { role: 'paste', label: L.paste },
        { role: 'selectAll', label: L.selectAll },
      ],
    },
    {
      label: L.view,
      submenu: [
        { role: 'reload', label: L.reload },
        { role: 'forceReload', label: L.forceReload },
        { role: 'toggleDevTools', label: L.toggleDevTools },
        { type: 'separator' },
        { role: 'resetZoom', label: L.resetZoom },
        { role: 'zoomIn', label: L.zoomIn },
        { role: 'zoomOut', label: L.zoomOut },
        { type: 'separator' },
        { role: 'togglefullscreen', label: L.togglefullscreen },
      ],
    },
    {
      label: L.window,
      submenu: [
        { role: 'minimize', label: L.minimize },
        { role: 'zoom', label: L.zoom },
        ...(isMac ? [] : [{ role: 'close', label: L.close }]),
      ],
    },
  ];
  return Menu.buildFromTemplate(template);
}

// Build a right-click context menu with basic text operations, tailored to the
// clicked element and translated to `lang`. Returns null when there is nothing
// useful to show. `params` is the object from the webContents 'context-menu' event.
function buildContextMenu(params, lang = currentLanguage) {
  const L = menuLabels(lang);
  const { editFlags, isEditable, selectionText } = params;
  const hasSelection = selectionText.trim().length > 0;
  const template = [];

  if (isEditable) {
    template.push(
      { role: 'undo', label: L.undo, enabled: editFlags.canUndo },
      { role: 'redo', label: L.redo, enabled: editFlags.canRedo },
      { type: 'separator' },
      { role: 'cut', label: L.cut, enabled: editFlags.canCut },
      { role: 'copy', label: L.copy, enabled: editFlags.canCopy },
      { role: 'paste', label: L.paste, enabled: editFlags.canPaste },
      { type: 'separator' },
      { role: 'selectAll', label: L.selectAll, enabled: editFlags.canSelectAll }
    );
  } else if (hasSelection) {
    template.push(
      { role: 'copy', label: L.copy, enabled: editFlags.canCopy },
      { type: 'separator' },
      { role: 'selectAll', label: L.selectAll, enabled: editFlags.canSelectAll }
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
    width: 1280,
    height: 800,
    minWidth: 1000,
    minHeight: 600,
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

  // A dead renderer process cannot be caught by the in-page error boundary, so
  // report it natively rather than leaving a blank window.
  mainWindow.webContents.on('render-process-gone', async (_event, details) => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const { response } = await dialog.showMessageBox(mainWindow, {
      type: 'error',
      title: 'Smart Classroom',
      message: 'The interface process stopped unexpectedly.',
      detail: `Reason: ${details.reason}${
        Number.isInteger(details.exitCode) ? ` (exit code ${details.exitCode})` : ''
      }\n\nBackend services are unaffected and keep running.`,
      buttons: ['Reload', 'Quit'],
      defaultId: 0,
      cancelId: 1,
    });
    if (response === 0) mainWindow.reload();
    else app.quit();
  });

  mainWindow.webContents.on('preload-error', (_event, preloadPath, error) => {
    console.error('[electron] preload script failed:', preloadPath, error);
  });

  mainWindow.once('ready-to-show', () => {
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

  // Renderer reports the surface currently covering the caption area (a modal,
  // the report panel, or nothing) so the overlay can be recoloured to match.
  ipcMain.on('titlebar:setTheme', (event, theme) => {
    if (process.platform === 'darwin') return;
    const win = BrowserWindow.fromWebContents(event.sender);
    if (!win || win.isDestroyed()) return;
    const colors = TITLE_BAR_THEMES[theme] || TITLE_BAR_THEMES.default;
    try {
      win.setTitleBarOverlay({ ...colors, height: TITLE_BAR_HEIGHT });
    } catch {
      // Overlay unavailable on this platform/frame — leave the caption alone.
    }
  });

  // Renderer reports its active language; rebuild the native application menu
  // in that language. The context menu reads `currentLanguage` at popup time,
  // so it needs no rebuild here.
  ipcMain.on('menu:setLanguage', (_event, lang) => {
    if (typeof lang !== 'string' || !lang) return;
    currentLanguage = lang;
    Menu.setApplicationMenu(buildAppMenu(currentLanguage));
  });

  // Open the OS-native file chooser (multi-select) and return the chosen files as
  // { path, name, size } records — size is read here so the renderer can show it in
  // the staging table without ever holding the file contents. Empty when cancelled.
  ipcMain.handle('dialog:pickFiles', async (event, options) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    const extensions = Array.isArray(options?.extensions) ? options.extensions : [];
    const dialogOptions = {
      properties: ['openFile', 'multiSelections'],
      ...(extensions.length ? { filters: [{ name: 'Supported files', extensions }] } : {}),
      ...(typeof options?.defaultPath === 'string' && options.defaultPath
        ? { defaultPath: options.defaultPath }
        : {}),
    };
    const result = win
      ? await dialog.showOpenDialog(win, dialogOptions)
      : await dialog.showOpenDialog(dialogOptions);
    if (result.canceled || !result.filePaths.length) return [];
    return result.filePaths.map((filePath) => {
      let size = 0;
      try {
        size = fs.statSync(filePath).size;
      } catch {
        // Unreadable file: report size 0 and let the backend reject it on ingest.
      }
      return { path: filePath, name: path.basename(filePath), size };
    });
  });

  // Open the OS-native folder chooser and return the selected absolute path
  // ('' when cancelled).
  ipcMain.handle('dialog:pickDirectory', async (event, defaultPath) => {
    const win = BrowserWindow.fromWebContents(event.sender);
    const options = {
      properties: ['openDirectory', 'createDirectory'],
      ...(typeof defaultPath === 'string' && defaultPath ? { defaultPath } : {}),
    };
    const result = win
      ? await dialog.showOpenDialog(win, options)
      : await dialog.showOpenDialog(options);
    if (result.canceled || !result.filePaths.length) return '';
    return result.filePaths[0];
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
