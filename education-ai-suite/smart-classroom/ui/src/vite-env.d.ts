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
  /** Backend process supervision. Absent in the plain web app. */
  services?: {
    list: () => Promise<import('./types/services').IpcResult<import('./types/services').ServiceSnapshot[]>>;
    start: (id: string) => Promise<import('./types/services').IpcResult<unknown>>;
    stop: (id: string) => Promise<import('./types/services').IpcResult<unknown>>;
    restart: (id: string) => Promise<import('./types/services').IpcResult<unknown>>;
    /** Returns an unsubscribe function. */
    onChanged: (callback: (snapshot: import('./types/services').ServiceSnapshot[]) => void) => () => void;
  };
  /** Captured stdout/stderr of managed services. Absent in the plain web app. */
  logs?: {
    read: (
      id: string,
      options?: { limit?: number; sinceSeq?: number }
    ) => Promise<import('./types/services').IpcResult<import('./types/services').LogLine[]>>;
    clear: (id: string) => Promise<import('./types/services').IpcResult<boolean>>;
    reveal: (id: string) => Promise<import('./types/services').IpcResult<string | null>>;
    /** Returns an unsubscribe function. */
    onAppend: (callback: (batch: import('./types/services').LogBatch) => void) => () => void;
  };
  /** Schema-guarded settings editor. Absent in the plain web app. */
  config?: {
    describe: () => Promise<import('./types/services').IpcResult<import('./types/config').ConfigDescription>>;
    apply: (
      changes: import('./types/config').ConfigChange[]
    ) => Promise<import('./types/services').IpcResult<{ written: string[]; skipped: number }>>;
    reveal: () => Promise<import('./types/services').IpcResult<string>>;
  };
  /** First-run setup runner. Absent in the plain web app. */
  setup?: {
    list: () => Promise<import('./types/services').IpcResult<import('./types/setup').SetupDescription>>;
    check: () => Promise<import('./types/services').IpcResult<import('./types/setup').SetupStep[]>>;
    run: (stepId: string, actionId: string) => Promise<import('./types/services').IpcResult<unknown>>;
    cancel: () => Promise<import('./types/services').IpcResult<boolean>>;
    logs: (options?: {
      limit?: number;
    }) => Promise<import('./types/services').IpcResult<import('./types/services').LogLine[]>>;
    clearLogs: () => Promise<import('./types/services').IpcResult<boolean>>;
    revealLogs: () => Promise<import('./types/services').IpcResult<string | null>>;
    /** Returns an unsubscribe function. */
    onChanged: (callback: (steps: import('./types/setup').SetupStep[]) => void) => () => void;
  };
  /** Clipboard via the main process; navigator.clipboard needs a secure context. */
  copyText: (text: string) => Promise<import('./types/services').IpcResult<boolean>>;
}

interface Window {
  electronAPI?: ElectronAPI;
}
