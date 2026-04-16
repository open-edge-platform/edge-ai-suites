import React, { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import "../../assets/css/MindMap.css";
import jsMind from "jsmind";
import "jsmind/style/jsmind.css";
import {
  clearMindmapStartRequest,
  mindmapStart as uiMindmapStart,
  mindmapSuccess as uiMindmapSuccess,
  mindmapFailed as uiMindmapFailed,
} from "../../redux/slices/uiSlice";

import {
  startMindmap as mmStart,
  setMindmap,
  setRendered,
  setSVG,
  setGenerationTime,
  setError,
  clearMindmap,
} from "../../redux/slices/mindmapSlice";

import { fetchMindmap } from "../../services/api";
import { useTranslation } from "react-i18next";

declare global {
  interface Window {
    jsMind: any;
  }
}

const activeMindmapSessions = new Set<string>();

const validateJsMindData = (data: any): boolean => {
  try {
    if (!data || typeof data !== 'object') return false;
    if (!data.meta || !data.format || !data.data) return false;
    if (data.format !== 'node_tree') return false;
    if (!data.data.id || !data.data.topic) return false;
    return true;
  } catch (error) {
    return false;
  }
};

/** Extracts the first balanced {...} block from a string. */
const extractFirstJsonObject = (text: string): string | null => {
  const start = text.indexOf("{");
  if (start === -1) return null;
  let depth = 0;
  let inString = false;
  let escape = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (escape) { escape = false; continue; }
    if (ch === "\\" && inString) { escape = true; continue; }
    if (ch === '"') { inString = !inString; continue; }
    if (inString) continue;
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return text.slice(start, i + 1);
    }
  }
  return null;
};

const tryParse = (s: string): any | null => {
  try {
    const p = JSON.parse(s);
    if (validateJsMindData(p)) return p;
  } catch {}
  return null;
};

const cleanJsMindContent = (content: string): any => {
  if (!content || !content.trim()) {
    return {
      "meta": { "name": "default", "author": "ai_assistant", "version": "1.0" },
      "format": "node_tree",
      "data": { "id": "root", "topic": "Main Topic", "children": [] }
    };
  }

  // Strategy 1: direct parse (handles clean JSON returned by backend)
  let result = tryParse(content.trim());
  if (result) return result;

  // Strategy 2: strip code fences then direct parse
  const stripped = content.replace(/```[a-zA-Z]*\n?([\s\S]*?)```/gs, "$1").trim();
  result = tryParse(stripped);
  if (result) return result;

  // Strategy 3: balanced-brace extractor on stripped content
  const extracted1 = extractFirstJsonObject(stripped);
  if (extracted1) {
    result = tryParse(extracted1);
    if (result) return result;
  }

  // Strategy 4: balanced-brace extractor on raw content (fallback if fence-strip corrupted it)
  const extracted2 = extractFirstJsonObject(content);
  if (extracted2) {
    result = tryParse(extracted2);
    if (result) return result;
  }

  console.error("cleanJsMindContent: all strategies failed. Raw content preview:", content.slice(0, 200));
  throw new Error("INVALID_FORMAT");
};

const MindMapTab: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();

  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const shouldStartMindmap = useAppSelector((s) => s.ui.shouldStartMindmap);
  const mindmapLoading = useAppSelector((s) => s.ui.mindmapLoading);
  const summaryComplete = useAppSelector((s) => s.ui.summaryComplete);

  const { finalText, isRendered, sessionId: mindmapSessionId } = useAppSelector((s) => s.mindmap);

  const startedRef = useRef(false);
  const shouldStartRef = useRef(false);
  const sessionRef = useRef<string | null>(null);
  const jsmindRef = useRef<HTMLDivElement>(null);
  const jsmindInstance = useRef<any>(null);
  const startTimeRef = useRef<number | null>(null);
  const isInitializedRef = useRef(false);

  // Refs for values read inside the fetch effect but that must NOT be deps
  const mindmapLoadingRef = useRef(false);
  const finalTextRef = useRef<string | null>(null);
  const mindmapSessionIdRef = useRef<string | null>(null);

  mindmapLoadingRef.current = mindmapLoading;
  finalTextRef.current = finalText ?? null;
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
    if (sessionRef.current && sessionRef.current !== sessionId) {
      activeMindmapSessions.delete(sessionRef.current);
      startedRef.current = false;
    }
    sessionRef.current = sessionId ?? null;
  }, [sessionId]);

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
        if (error.message === "INVALID_FORMAT") {
          isInvalidFormat = true;
          mindData = {
            "meta": {
              "name": "error_fallback",
              "author": "ai_assistant", 
              "version": "1.0"
            },
            "format": "node_tree",
            "data": {
              "id": "root",
              "topic": "Error: Invalid Format",
              "children": [
                {
                  "id": "error_msg",
                  "topic": "Failed to parse mindmap data"
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

      if (startTimeRef.current && !isRendered) {
        dispatch(setGenerationTime(performance.now() - startTimeRef.current));
      }

      if (!isRendered) {
        dispatch(setRendered(true));
      }
      if (isInvalidFormat) {
        dispatch(setError("MindMap generation failed due to invalid format"));
        dispatch(uiMindmapFailed());
        window.dispatchEvent(
          new CustomEvent("global-notification", {
            detail: {
              message: t("notifications.mindmapError") || "MindMap generation failed due to invalid format.",
              type: "error",
            },
          })
        );
      }

    } catch (error: any) {
      console.error("❌ jsMind render error:", error);

      dispatch(setError("Mindmap rendering failed"));
      dispatch(setRendered(true));
      dispatch(uiMindmapFailed());
    }
  };

  // Keep a ref in sync with shouldStartMindmap so we can read it inside effects
  // without adding it to dependency arrays (prevents the self-triggering loop).
  useEffect(() => {
    shouldStartRef.current = shouldStartMindmap;
  }, [shouldStartMindmap]);

  useEffect(() => {
    if (!mindmapEnabled || !sessionId) return;
    if (!shouldStartRef.current) return;
    if (!summaryComplete) return;
    // Already have result for this session (read via ref — not a dep)
    if (mindmapSessionIdRef.current === sessionId && finalTextRef.current) return;
    // Redux-level guard: already fetching (read via ref — not a dep)
    if (mindmapLoadingRef.current) return;
    // Component/module-level guards
    if (activeMindmapSessions.has(sessionId) || startedRef.current) return;

    startedRef.current = true;
    activeMindmapSessions.add(sessionId);
    startTimeRef.current = performance.now();

    dispatch(mmStart(sessionId));
    // Clear the trigger flag BEFORE the async call to stop re-entry.
    // Do NOT dispatch uiMindmapStart here — it sets shouldStartMindmap=true
    // again, which causes the effect to re-fire and hit the backend repeatedly.
    dispatch(clearMindmapStartRequest());

    (async () => {
      try {
        const fullMindmap = await fetchMindmap(sessionId);

        if (typeof fullMindmap === "string" && fullMindmap.length > 0) {
          dispatch(setMindmap(fullMindmap));
          dispatch(uiMindmapSuccess());
        } else {
          throw new Error("Empty mindmap returned");
        }
      } catch (err: any) {
        console.error("❌ Mindmap fetch error:", err);
        dispatch(setError(err.message || "Mindmap generation failed"));
        dispatch(uiMindmapFailed());
      } finally {
        dispatch(clearMindmapStartRequest());
      }
    })();
  }, [mindmapEnabled, sessionId, summaryComplete, dispatch]);

  useEffect(() => {
    isInitializedRef.current = false;
    startedRef.current = false;
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