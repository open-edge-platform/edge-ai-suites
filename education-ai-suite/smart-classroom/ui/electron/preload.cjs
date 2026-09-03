// Minimal preload bridge. Kept intentionally small so the React app never
// hard-depends on it: any Electron-only feature in src/ must be feature-detected
// via `window.electronAPI?.isElectron`, preserving plain web-app parity.

const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  version: process.env.npm_package_version || '',
  // Host platform ('win32' | 'darwin' | 'linux').
  platform: process.platform,
  // Open the native application menu (File/Edit/View/Window) as a popup.
  // `position` is the desired top-left in viewport pixels.
  popupMenu: (position) => ipcRenderer.send('menu:popup', position),
  // Tell the main process which language to render the native menus in
  // (application menu + right-click context menu). Call on language change.
  setLanguage: (lang) => ipcRenderer.send('menu:setLanguage', lang),
  // Recolour the native title bar overlay to match whatever is covering the
  // caption area: 'dimmed' behind a modal, 'light' behind the report panel,
  // 'default' for the app header.
  setTitleBarTheme: (theme) => ipcRenderer.send('titlebar:setTheme', theme),
  // Open the OS-native folder chooser, optionally starting at `defaultPath`.
  // Resolves to the selected absolute path, or '' if the user cancelled.
  pickDirectory: (defaultPath) => ipcRenderer.invoke('dialog:pickDirectory', defaultPath),
  // Open the OS-native file chooser (multi-select). `options.extensions` filters the
  // dialog (e.g. ['mp4','pdf']). Resolves to [{ path, name, size }], [] if cancelled.
  pickFiles: (options) => ipcRenderer.invoke('dialog:pickFiles', options),
  // Resolve the absolute filesystem path of a File chosen via <input type=file>
  // or drag-and-drop. Electron-only; Returns '' if resolution fails.
  getPathForFile: (file) => {
    try {
      return webUtils.getPathForFile(file);
    } catch {
      return '';
    }
  },

  // Backend process supervision. Every call resolves to { ok, data } | { ok, error };
  // `id` must be one of the ids returned by services.list().
  services: {
    list: () => ipcRenderer.invoke('services:list'),
    start: (id) => ipcRenderer.invoke('services:start', id),
    stop: (id) => ipcRenderer.invoke('services:stop', id),
    restart: (id) => ipcRenderer.invoke('services:restart', id),
    // Subscribe to status changes; returns an unsubscribe function.
    onChanged: (callback) => {
      const listener = (_event, snapshot) => callback(snapshot);
      ipcRenderer.on('services:changed', listener);
      return () => ipcRenderer.removeListener('services:changed', listener);
    },
  },

  // Captured stdout/stderr of managed services.
  logs: {
    read: (id, options) => ipcRenderer.invoke('logs:read', id, options),
    clear: (id) => ipcRenderer.invoke('logs:clear', id),
    reveal: (id) => ipcRenderer.invoke('logs:reveal', id),
    // Batches of new lines: { id, lines: [{ seq, ts, stream, text }] }.
    onAppend: (callback) => {
      const listener = (_event, batch) => callback(batch);
      ipcRenderer.on('logs:append', listener);
      return () => ipcRenderer.removeListener('logs:append', listener);
    },
  },

  // Editable settings from config.yaml, runtime_config.yaml and .proxy-config.
  // Only paths in the main-process schema allowlist can be read or written.
  config: {
    describe: () => ipcRenderer.invoke('config:describe'),
    apply: (changes) => ipcRenderer.invoke('config:apply', changes),
    reveal: () => ipcRenderer.invoke('config:reveal'),
  },

  // First-run setup. `id` must be one of the ids returned by setup.list().
  setup: {
    list: () => ipcRenderer.invoke('setup:list'),
    check: () => ipcRenderer.invoke('setup:check'),
    run: (stepId, actionId) => ipcRenderer.invoke('setup:run', stepId, actionId),
    cancel: () => ipcRenderer.invoke('setup:cancel'),
    logs: (options) => ipcRenderer.invoke('setup:logs', options),
    clearLogs: () => ipcRenderer.invoke('setup:clearLogs'),
    revealLogs: () => ipcRenderer.invoke('setup:revealLogs'),
    // Subscribe to step status changes; returns an unsubscribe function.
    onChanged: (callback) => {
      const listener = (_event, snapshot) => callback(snapshot);
      ipcRenderer.on('setup:changed', listener);
      return () => ipcRenderer.removeListener('setup:changed', listener);
    },
  },

  // Copy through the main process: navigator.clipboard needs a secure context,
  // which a packaged build loaded over file:// is not.
  copyText: (text) => ipcRenderer.invoke('app:copyText', text),
});
