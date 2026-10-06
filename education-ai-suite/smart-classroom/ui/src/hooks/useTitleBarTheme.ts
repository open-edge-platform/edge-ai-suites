import { useEffect } from 'react';

/**
 * Recolours the Electron title bar overlay while a surface covers the caption.
 *
 * The Window Controls Overlay strip is painted by Windows, not by the page, so
 * no DOM overlay can dim or hide it. Left alone, anything that darkens the UI —
 * a modal, or a slide-over panel's backdrop — leaves a bright blue patch with
 * white glyphs above it.
 *
 * No-op on the plain web app and on any platform without WCO — the preload
 * bridge is absent or the main process ignores the message.
 */
export type TitleBarTheme = 'default' | 'dimmed';

/**
 * LIFO rather than a simple counter: when a dialog opens over the report panel
 * both ask for `dimmed`, and closing the dialog must fall back to the panel's
 * entry rather than dropping straight to `default` while the panel is still up.
 */
const stack: Array<{ id: object; theme: TitleBarTheme }> = [];

function applyTopmost() {
  const top = stack[stack.length - 1];
  window.electronAPI?.setTitleBarTheme?.(top ? top.theme : 'default');
}

export function useTitleBarTheme(active: boolean, theme: TitleBarTheme) {
  useEffect(() => {
    if (!active) return;
    const entry = { id: {}, theme };
    stack.push(entry);
    applyTopmost();
    return () => {
      const index = stack.findIndex((e) => e.id === entry.id);
      if (index >= 0) stack.splice(index, 1);
      applyTopmost();
    };
  }, [active, theme]);
}
