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
  // Resolve the absolute filesystem path of a File chosen via <input type=file>
  // or drag-and-drop. Electron-only; Returns '' if resolution fails.
  getPathForFile: (file) => {
    try {
      return webUtils.getPathForFile(file);
    } catch {
      return '';
    }
  },
});
