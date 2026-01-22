import React, { useEffect, useRef } from "react";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import "../../assets/css/MindMap.css";
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
import "../../assets/css/MindMap.css";
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

const cleanJsMindContent = (content: string): any => {
  if (!content) {
    return {
      "meta": {
        "name": "default",
        "author": "ai_assistant",
        "version": "1.0"
      },
      "format": "node_tree",
      "data": {
        "id": "root",
        "topic": "Main Topic",
        "children": []
      }
    };
  }

  try {
    const cleanedContent = content.replace(/```[a-zA-Z]*\n?([\s\S]*?)```/g, "$1").trim();
    const parsedData = JSON.parse(cleanedContent);
    if (validateJsMindData(parsedData)) {
      return parsedData;
    } else {
      throw new Error("Invalid jsMind format");
    }
  } catch (error) {
    console.error("Failed to parse jsMind data:", error);
    throw new Error("INVALID_FORMAT");
  }
};

const MindMapTab: React.FC = () => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();

  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const shouldStartMindmap = useAppSelector((s) => s.ui.shouldStartMindmap);
  const summaryComplete = useAppSelector((s) => s.ui.summaryComplete);

  const { finalText, isRendered, sessionId: mindmapSessionId } = useAppSelector((s) => s.mindmap);

  const startedRef = useRef(false);
  const sessionRef = useRef<string | null>(null);
  const jsmindRef = useRef<HTMLDivElement>(null);
  const jsmindInstance = useRef<any>(null);
  const startTimeRef = useRef<number | null>(null);
  const isInitializedRef = useRef(false);

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
    const loadJsMind = async () => {
      if (window.jsMind) return;
      const cssLink = document.createElement('link');
      cssLink.rel = 'stylesheet';
      cssLink.href = '//cdn.jsdelivr.net/npm/jsmind@0.8.5/style/jsmind.css';
      document.head.appendChild(cssLink);
      const script = document.createElement('script');
      script.src = '//cdn.jsdelivr.net/npm/jsmind@0.8.5/es6/jsmind.js';
      script.onload = () => {
        console.log('jsMind loaded successfully');
      };
      script.onerror = () => {
        console.error('Failed to load jsMind');
      };
      document.head.appendChild(script);
    };

    loadJsMind();
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

  useEffect(() => {
    if (!mindmapEnabled || !sessionId || !shouldStartMindmap) return;
    if (!summaryComplete) {
      console.log('🧠 Waiting for summary to complete before starting mindmap');
      return;
    }
    if (mindmapSessionId === sessionId && finalText) {
      return;
    }
    
    if (activeMindmapSessions.has(sessionId) || startedRef.current) return;
    startedRef.current = true;
    activeMindmapSessions.add(sessionId);
    startTimeRef.current = performance.now();

    dispatch(mmStart(sessionId));
    dispatch(clearMindmapStartRequest());
    dispatch(uiMindmapStart());

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
  }, [mindmapEnabled, shouldStartMindmap, sessionId, dispatch, mindmapSessionId, finalText, summaryComplete]);

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