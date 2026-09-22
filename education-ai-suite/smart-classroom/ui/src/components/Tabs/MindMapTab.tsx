import React, { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import "../../assets/css/MindMap.css";
import jsMind from "jsmind";
import "jsmind/style/jsmind.css";
import html2canvas from "html2canvas";
import {
  mindmapFailed as uiMindmapFailed,
  mindmapImageDone as uiMindmapImageDone,
} from "../../redux/slices/uiSlice";

import {
  setRendered,
  setGenerationTime,
  setError,
} from "../../redux/slices/mindmapSlice";

import { uploadMindmapImage } from "../../services/api";
import { useTranslation } from "react-i18next";
import { useFeatureConfig } from "../../hooks/useFeatureConfig";
import { INVALID_FORMAT, cleanJsMindContent } from "../../utils/jsmindData";

declare global {
  interface Window {
    jsMind: any;
  }
}

// Renders the mind map the pipeline fetched into the store (see
// redux/useAudioPipeline), and — because both need the rendered DOM — takes the
// screenshot the report embeds. The fetch is not owned here: this tab is
// unmounted whenever another tab is selected, so a mind map may already be in
// the store by the time it first mounts.
const MindMapTab: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const { guard: featureGuard } = useFeatureConfig();

  const sessionId = useAppSelector((s) => s.ui.sessionId);

  const { finalText, isRendered, startedAt, sessionId: mindmapSessionId } = useAppSelector((s) => s.mindmap);

  const jsmindRef = useRef<HTMLDivElement>(null);
  const jsmindInstance = useRef<any>(null);
  const isInitializedRef = useRef(false);
  // Ensures the screenshot is captured/uploaded (and the session marked complete)
  // exactly once per session, even though renderMindmap re-runs on tab re-mounts.
  const capturedRef = useRef(false);

  const mindmapSessionIdRef = useRef<string | null>(null);
  mindmapSessionIdRef.current = mindmapSessionId ?? null;

  const cleanupJsMind = () => {
    try {
      if (jsmindInstance.current) {
        if (typeof jsmindInstance.current.remove === 'function') {
          jsmindInstance.current.remove();
        } else if (typeof jsmindInstance.current.destroy === 'function') {
          jsmindInstance.current.destroy();
        } else if (typeof jsmindInstance.current.clear === 'function') {
          jsmindInstance.current.clear();
        }
        jsmindInstance.current = null;
      }
      
      if (jsmindRef.current) {
        jsmindRef.current.innerHTML = '';
      }
    } catch (error) {
      console.warn('Error during jsMind cleanup:', error);
      if (jsmindRef.current) {
        jsmindRef.current.innerHTML = '';
      }
      jsmindInstance.current = null;
    }
  };

  useEffect(() => {
    if (!window.jsMind) {
      window.jsMind = jsMind;
    }
  }, []);

  useEffect(() => {
    if (!finalText || !jsmindRef.current) return;
    if (isRendered && !isInitializedRef.current) {
      renderMindmap();
      return;
    }
    if (!isRendered) {
      renderMindmap();
    }
  }, [finalText, isRendered]);

  const renderMindmap = async () => {
    let isInvalidFormat = false;
    
    try {
      let attempts = 0;
      while (!window.jsMind && attempts < 50) {
        await new Promise(resolve => setTimeout(resolve, 100));
        attempts++;
      }

      if (!window.jsMind) {
        throw new Error("jsMind library not loaded");
      }

      let mindData;
      try {
        mindData = cleanJsMindContent(finalText || ' ');
      } catch (error: any) {
        if (error.message === INVALID_FORMAT) {
          isInvalidFormat = true;
          mindData = {
            "meta": {
              "name": "error_fallback",
              "author": "ai_assistant", 
              "version": "1.0"
            },
            "format": "node_tree",
            // Rendered in place of the mind map, so both topics are translated.
            "data": {
              "id": "root",
              "topic": t("mindmap.invalidFormatTitle"),
              "children": [
                {
                  "id": "error_msg",
                  "topic": t("mindmap.invalidFormatDetail")
                }
              ]
            }
          };
        } else {
          throw error;
        }
      }
      cleanupJsMind();
      const options = {
        container: jsmindRef.current,
        theme: 'primary',
        editable: true,
        mode: 'full',
        view: {
          engine: 'svg',
          hmargin: 120,        
          vmargin: 60,         
          line_width: 2,
          line_color: '#555',  
          draggable: true,
          hide_scrollbars_when_draggable: false,
          line_style: 'curved',
          node_overflow: 'wrap', 
          expander_style: 'char'
        },
      };

      jsmindInstance.current = new window.jsMind(options);
      jsmindInstance.current.show(mindData);

      isInitializedRef.current = true;

      // Measured from where the fetch was kicked off (useAudioPipeline) through
      // to this first render.
      if (startedAt && !isRendered) {
        dispatch(setGenerationTime(performance.now() - startedAt));
      }

      if (!isRendered) {
        dispatch(setRendered(true));
      }
      if (isInvalidFormat) {
        dispatch(setError("MindMap generation failed due to invalid format"));
        dispatch(uiMindmapFailed());
      } else if (featureGuard?.hasFeature('report')) {
        // The report embeds the mind map as an image captured here (html2canvas)
        // from the live jsMind view — the backend never re-renders it. Best-effort
        // and fire-and-forget: a failure just omits the image from the report.
        captureAndUploadMindmap();
      } else {
        dispatch(uiMindmapImageDone());
      }

    } catch (error: any) {
      console.error("❌ jsMind render error:", error);

      dispatch(setError("Mindmap rendering failed"));
      dispatch(setRendered(true));
      dispatch(uiMindmapFailed());
    }
  };

  // Screenshot the rendered jsMind view and upload it as the report's mind-map
  // image. Runs once per session (capturedRef); waits a beat for the SVG lines +
  // nodes to paint, resets the view to 1× zoom scrolled to the origin so the
  // WHOLE map (starting at the root) is captured, then screenshots the inner
  // canvas at jsMind's own reported layout size.
  //
  // We rely on jsMind's `view.size` (the full laid-out map size incl. margins)
  // instead of measuring getBoundingClientRect() and manually translating the
  // SVG/node layers: while the user has panned/zoomed the map, those viewport
  // coords are offset from the layers' own coordinate space, which is what made
  // the old capture crop the root node and look jumbled.
  //
  // Always dispatches mindmapImageDone (success OR failure) so report
  // auto-generation is unblocked either way.
  const captureAndUploadMindmap = async () => {
    const sid = mindmapSessionIdRef.current;
    if (capturedRef.current) return;
    if (!sid) {
      // No session to upload to — don't block the report waiting for an image.
      dispatch(uiMindmapImageDone());
      return;
    }
    capturedRef.current = true;

    // Snapshot the current view transform so we can restore the user's pan/zoom.
    const jm = jsmindInstance.current;
    const inner = jsmindRef.current?.querySelector<HTMLElement>(".jsmind-inner");
    const prevZoom = jm?.view?.zoom_current ?? 1;
    const prevScrollLeft = inner?.scrollLeft ?? 0;
    const prevScrollTop = inner?.scrollTop ?? 0;

    // Saved so we can restore the scroll container's own box after capture.
    let prevInnerWidth = "";
    let prevInnerHeight = "";
    let prevInnerOverflow = "";
    let expanded = false;

    try {
      // Let layout/paint settle so node coordinates and connector lines are final.
      await new Promise(resolve => setTimeout(resolve, 400));
      await new Promise(resolve => requestAnimationFrame(() => resolve(null)));
      await new Promise(resolve => requestAnimationFrame(() => resolve(null)));

      if (!inner) throw new Error("jsMind inner element not found");

      // Reset to 1× zoom and scroll to the origin so html2canvas captures from
      // the top-left of the full map (the root node) with a stable coord system.
      try {
        if (jm?.view && typeof jm.view.set_zoom === "function" && prevZoom !== 1) {
          jm.view.set_zoom(1);
        }
      } catch { /* zoom reset is best-effort */ }
      inner.scrollLeft = 0;
      inner.scrollTop = 0;

      // Full laid-out map size as jsMind computed it (includes hmargin/vmargin
      // as built-in padding). Fall back to the scroll size if unavailable.
      const size = jm?.view?.size;
      const targetWidth = Math.max(1, Math.ceil(size?.w || inner.scrollWidth));
      const targetHeight = Math.max(1, Math.ceil(size?.h || inner.scrollHeight));

      // .jsmind-inner is the SCROLL container: its own box is only the visible
      // panel (width/height 100%, overflow auto), so html2canvas would clip
      // anything past the viewport — cropping the right/bottom of a wide map.
      // Temporarily grow its box to the full map size and expose overflow so the
      // whole tree is inside the captured region, then restore below.
      prevInnerWidth = inner.style.width;
      prevInnerHeight = inner.style.height;
      prevInnerOverflow = inner.style.overflow;
      inner.style.width = `${targetWidth}px`;
      inner.style.height = `${targetHeight}px`;
      inner.style.overflow = "visible";
      expanded = true;

      await new Promise(resolve => requestAnimationFrame(() => resolve(null)));

      const canvas = await html2canvas(inner, {
        backgroundColor: "#ffffff",
        scale: 2, // sharper image in the .docx
        width: targetWidth,
        height: targetHeight,
        windowWidth: targetWidth,
        windowHeight: targetHeight,
        scrollX: 0,
        scrollY: 0,
        useCORS: true,
      });

      const blob: Blob | null = await new Promise(resolve =>
        canvas.toBlob(resolve, "image/png")
      );
      if (!blob) throw new Error("Failed to encode mind-map PNG");

      await uploadMindmapImage(sid, blob);
      dispatch(uiMindmapImageDone());
    } catch (err) {
      // Non-fatal: the report just renders without the mind-map image. Still
      // signal done so report auto-generation isn't blocked forever.
      console.warn("Mind-map screenshot upload failed:", err);
      capturedRef.current = false;  // allow a retry on a later re-render
      dispatch(uiMindmapImageDone());
    } finally {
      // Restore the scroll container's own box.
      if (inner && expanded) {
        inner.style.width = prevInnerWidth;
        inner.style.height = prevInnerHeight;
        inner.style.overflow = prevInnerOverflow;
      }
      // Restore the user's original pan/zoom.
      try {
        if (jm?.view && typeof jm.view.set_zoom === "function" && prevZoom !== 1) {
          jm.view.set_zoom(prevZoom);
        }
      } catch { /* best-effort */ }
      if (inner) {
        inner.scrollLeft = prevScrollLeft;
        inner.scrollTop = prevScrollTop;
      }
    }
  };

  useEffect(() => {
    isInitializedRef.current = false;
    capturedRef.current = false;
  }, [sessionId]);

  useEffect(() => {
    return () => {
      cleanupJsMind();
      isInitializedRef.current = false;
    };
  }, []);

  return (
    <div className="mindmap-tab-fullscreen">
      <div className="mindmap-wrapper-fullscreen">
        <div className="mindmap-content-fullscreen">
          <div 
            ref={jsmindRef} 
            className="jsmind-container-fullscreen"
          />
        </div>
      </div>
    </div>
  );
};

export default MindMapTab;