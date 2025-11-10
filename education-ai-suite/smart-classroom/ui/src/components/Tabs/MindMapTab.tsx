import React, { useEffect, useRef } from "react";
import mermaid from "mermaid";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import {
  firstMindmapToken,
  mindmapDone,
  clearMindmapStartRequest,
} from "../../redux/slices/uiSlice";
import {
  appendMindmap,
  finishMindmap,
  startMindmap,
  setRendered,
  setSVG, 
  setGenerationTime,
} from "../../redux/slices/mindmapSlice";
import { streamMindmap } from "../../services/api";
import "../../assets/css/MindMap.css";

const activeMindmapSessions = new Set<string>();

const cleanMindmapContent = (content: string): string => {
  if (!content) return "mindmap\n  root((Main Topic))";

  content = content.replace(/```[\s\S]*?```/g, "").replace(/```/g, "").trim();

  if (!/^mindmap/.test(content)) {
    content = "mindmap\n" + content;
  }
  content = content.replace(
    /root\(\((.*?)\)\)/g,
    (match, label) => `root(("${label.trim()}"))`
  );

  return content;
};

const MindMapTab: React.FC = () => {
  const dispatch = useAppDispatch();

  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const shouldStartMindmap = useAppSelector((s) => s.ui.shouldStartMindmap);
  const { finalText, isRendered, svg } = useAppSelector((s) => s.mindmap);
  const startedRef = useRef(false);
  const mermaidRef = useRef<HTMLDivElement>(null);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: "default",
      securityLevel: "loose",
      flowchart: { useMaxWidth: true, htmlLabels: true },
      mindmap: { useMaxWidth: true },
    });
  }, []);

  useEffect(() => {
    if (svg && mermaidRef.current && !mermaidRef.current.innerHTML) {
      mermaidRef.current.innerHTML = svg;
    }
  }, [svg]);

  useEffect(() => {
    if (!finalText || !mermaidRef.current || isRendered) return;

    const renderMermaid = async () => {
      try {
        const cleaned = cleanMindmapContent(finalText);
        const { svg } = await mermaid.render("diagram-" + Date.now(), cleaned);
        mermaidRef.current!.innerHTML = svg;

        dispatch(setSVG(svg));

        if (startTimeRef.current) {
          const end = performance.now();
          const duration = end - startTimeRef.current;
          dispatch(setGenerationTime(duration));
          console.log(`🕒 Mindmap generated in ${(duration / 1000).toFixed(2)}s`);
        }

        dispatch(setRendered(true));
      } catch (error) {
        console.error("❌ Mermaid render error:", error);
        mermaidRef.current!.innerHTML = `
          <div class="mermaid-error">
            ⚠️ Error rendering diagram. Please check your input format.
          </div>`;
        dispatch(setRendered(true)); 
      }
    };

    renderMermaid();
  }, [finalText, dispatch, isRendered]);


  useEffect(() => {
    if (!mindmapEnabled || !sessionId || !shouldStartMindmap) return;
    if (activeMindmapSessions.has(sessionId) || startedRef.current) return;

    startedRef.current = true;
    activeMindmapSessions.add(sessionId);
    startTimeRef.current = performance.now();
    dispatch(clearMindmapStartRequest());
    dispatch(startMindmap());

    (async () => {
      try {
        let sentFirst = false;
        let fullContent = "";

        for await (const ev of streamMindmap(sessionId)) {
          if (ev.type === "mindmap_token") {
            if (!sentFirst) {
              dispatch(firstMindmapToken());
              sentFirst = true;
            }
            fullContent += ev.token;
          } else if (ev.type === "error") {
            window.dispatchEvent(
              new CustomEvent("global-error", {
                detail: ev.message || "Mindmap generation error",
              })
            );
            break;
          } else if (ev.type === "done") {
            dispatch(appendMindmap(fullContent));
            break;
          }
        }
      } catch (e: any) {
        if (e?.name !== "AbortError") console.error("Stream error", e);
      } finally {
        dispatch(finishMindmap());
        dispatch(mindmapDone());
      }
    })();
  }, [mindmapEnabled, shouldStartMindmap, sessionId, dispatch]);


  return (
    <div className="mindmap-tab">

      {!isRendered && (
        <div className="mindmap-loading">
          <span className="tab-spinner" aria-label="loading" />
          <p>Generating mindmap…</p>
        </div>
      )}

      <div
        className="mindmap-wrapper"
        style={{ display: isRendered ? "flex" : "none" }}
      >
        <div className="mindmap-content">
          <div ref={mermaidRef} className="mermaid-container" />
        </div>
      </div>
    </div>
  );
};

export default MindMapTab;
