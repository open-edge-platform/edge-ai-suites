/// <reference types="vite/client" />

// Bridge exposed by the Electron preload (electron/preload.cjs). Optional so the
// plain web app (where it is undefined) still type-checks. Always feature-detect.
interface ElectronAPI {
  isElectron: boolean;
  version: string;
  /** Host platform: 'win32' | 'darwin' | 'linux'. */
  platform: string;
  /** Open the native application menu as a popup at the given viewport point. */
  popupMenu: (position?: { x: number; y: number }) => void;
  /** Absolute filesystem path for a File chosen in Electron; '' if unavailable. */
  getPathForFile: (file: File) => string;
}

interface Window {
  electronAPI?: ElectronAPI;
}
