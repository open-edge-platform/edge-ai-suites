import React, { useEffect, useRef } from "react";
import mermaid from "mermaid";
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

const activeMindmapSessions = new Set<string>();

const cleanMindmapContent = (content: string): string => {
  if (!content) return "mindmap\n  root((Main Topic))";
  content = content.replace(/```[a-zA-Z]*\n?([\s\S]*?)```/g, "$1").trim();
  if (!/^mindmap/.test(content)) {
    content = "mindmap\n" + content;
  }

  const wrapText = (text: string, maxLength: number = 25): string => {
    if (text.length <= maxLength) return text;
    
    const words = text.split(' ');
    const lines: string[] = [];
    let currentLine = '';
    
    for (const word of words) {
      if ((currentLine + ' ' + word).length <= maxLength) {
        currentLine = currentLine ? currentLine + ' ' + word : word;
      } else {
        if (currentLine) lines.push(currentLine);
        currentLine = word;
      }
    }
    if (currentLine) lines.push(currentLine);
    
    return lines.join('<br/>');
  };

  content = content
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => {
      let cleaned = line.replace(/\s+$/g, "");
      cleaned = cleaned.replace(/^(\s*)[-*•]\s+/, "$1");
      cleaned = cleaned.replace(/\t/g, "  ");
      
      const match = cleaned.match(/^(\s*)(.*?)(\s*\([^)]*\)\s*)?$/);
      if (match && match[2]) {
        const indent = match[1] || '';
        const text = match[2];
        const suffix = match[3] || '';
        
        if (!text.includes('<br/>') && text.length > 25) {
          const wrappedText = wrapText(text);
          cleaned = indent + wrappedText + suffix;
        }
      }
      
      return cleaned;
    })
    .join("\n");
  content = content.replace(/root\s*\(\(\s*(.*?)\s*\)\)/, (match, label) => {
    const wrappedLabel = wrapText(label, 30); 
    return `root((${wrappedLabel}))`;
  });

  return content.trim();
};

const MindMapTab: React.FC = () => {
  const dispatch = useAppDispatch();

  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const shouldStartMindmap = useAppSelector((s) => s.ui.shouldStartMindmap);

  const { finalText, isRendered, svg, isLoading } = useAppSelector(
    (s) => s.mindmap
  );

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
            ⚠️ Error rendering diagram. Please check the input format.
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
    dispatch(clearMindmap());
    dispatch(clearMindmapStartRequest());
    dispatch(uiMindmapStart()); 
    dispatch(mmStart()); 

    (async () => {
      try {
        const fullMindmap = await fetchMindmap(sessionId);

        if (typeof fullMindmap === "string" && fullMindmap.length > 0) {
          dispatch(setMindmap(fullMindmap)); 
          dispatch(uiMindmapSuccess()); 
        } else {
          throw new Error("Empty mindmap returned from server.");
        }
      } catch (err: any) {
        console.error("❌ Mindmap fetch error:", err);
        const message = err?.message || "Mindmap generation failed";
        dispatch(setError(message)); 
        dispatch(uiMindmapFailed()); 
        mermaidRef.current!.innerHTML = `
          <div class="mermaid-error">
            ⚠️ Failed to generate mindmap: ${message}
          </div>`;
      } finally {
        dispatch(clearMindmapStartRequest());
      }
    })();
  }, [mindmapEnabled, shouldStartMindmap, sessionId, dispatch]);

  return (
    <div className="mindmap-tab">
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
