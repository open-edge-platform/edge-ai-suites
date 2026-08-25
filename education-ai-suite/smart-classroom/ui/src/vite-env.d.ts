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
  /** Set the language for the native menus (application + context menu). */
  setLanguage: (lang: string) => void;
  /**
   * Recolour the native title bar overlay to match the surface covering the
   * caption area.
   */
  setTitleBarTheme: (theme: 'default' | 'dimmed' | 'light') => void;
  /**
   * Open the OS-native folder chooser, optionally starting at `defaultPath`.
   * Resolves to the chosen absolute path, or '' if the user cancelled.
   */
  pickDirectory: (defaultPath?: string) => Promise<string>;
  /**
   * Open the OS-native file chooser (multi-select). Resolves to the chosen files,
   * or an empty array if the user cancelled.
   */
  pickFiles: (options?: {
    extensions?: string[];
    defaultPath?: string;
  }) => Promise<Array<{ path: string; name: string; size: number }>>;
  /** Absolute filesystem path for a File chosen in Electron; '' if unavailable. */
  getPathForFile: (file: File) => string;
}

interface Window {
  electronAPI?: ElectronAPI;
}
