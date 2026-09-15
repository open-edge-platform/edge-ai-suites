import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

/**
 * Tracks the x offset (relative to the container) of the right panel's left edge,
 * so the collapse toggle can sit exactly on the divider.
 *
 * Measuring is necessary because the divider is NOT at 50%: the left panel carries
 * horizontal padding while the right slot does not, and with `flex-basis: 0` +
 * `border-box` it cannot shrink below that padding — so it ends up wider by the
 * padding amount, pushing the divider half of it off-centre (~15px on the main
 * screen).
 *
 * Returns refs for the container and the right panel, the toggle's `left` value,
 * and a `transition` override used to suppress the CSS slide while resizing.
 */
export function usePanelDividerX(...deps: unknown[]) {
  const containerRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef(0);
  const [state, setState] = useState<{ x: number | null; animate: boolean }>({
    x: null,
    animate: true,
  });

  const measure = useCallback((animate: boolean) => {
    // Coalesce bursts of ResizeObserver callbacks into one measurement per frame,
    // so dragging the window edge doesn't trigger a re-render per event.
    cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(() => {
      const container = containerRef.current;
      const panel = panelRef.current;
      if (!container || !panel) return;
      const x = panel.getBoundingClientRect().left - container.getBoundingClientRect().left;
      setState((prev) => (prev.x === x && prev.animate === animate ? prev : { x, animate }));
    });
  }, []);

  // Re-measure when the layout changes for a reason we know about (collapsing,
  // switching views). These are discrete user actions, so keep the slide animation.
  useLayoutEffect(() => {
    measure(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [measure, ...deps]);

  // Continuous changes (window resize, panel content growing). Animating here
  // would make the toggle visibly trail the divider by the transition duration,
  // so these updates are applied instantly.
  useEffect(() => {
    const container = containerRef.current;
    const panel = panelRef.current;
    if (!container || !panel) return;

    const onResize = () => measure(false);
    const observer = new ResizeObserver(onResize);
    observer.observe(container);
    observer.observe(panel);
    window.addEventListener('resize', onResize);

    return () => {
      cancelAnimationFrame(frameRef.current);
      observer.disconnect();
      window.removeEventListener('resize', onResize);
    };
  }, [measure]);

  /** Half the toggle's 28px width, so it straddles the divider. */
  const ARROW_HALF = 14;

  return {
    containerRef,
    panelRef,
    arrowLeft: state.x === null ? 'calc(50% - 14px)' : `${state.x - ARROW_HALF}px`,
    /** Pass to the toggle's style so resize-driven moves don't animate. */
    arrowTransition: state.animate ? undefined : 'none',
  };
}
