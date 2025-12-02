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
import { useTranslation } from "react-i18next";

const activeMindmapSessions = new Set<string>();

const cleanMindmapContent = (content: string): string => {
  if (!content) return "mindmap\n  root((Main Topic))";
  content = content.replace(/```[a-zA-Z]*\n?([\s\S]*?)```/g, "$1").trim();
  if (!/^mindmap/.test(content)) {
    content = "mindmap\n" + content;
  }
  const wrapText = (text: string, maxLength: number = 25): string => {
    if (text.length <= maxLength) return text;
    const words = text.split(" ");
    const lines: string[] = [];
    let currentLine = "";
    for (const word of words) {
      if ((currentLine + " " + word).trim().length <= maxLength) {
        currentLine = currentLine ? currentLine + " " + word : word;
      } else {
        if (currentLine) lines.push(currentLine);
        currentLine = word;
      }
    }
    if (currentLine) lines.push(currentLine);
    return lines.join("<br/>");
  };
  content = content
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => {
      let cleaned = line.replace(/\s+$/g, "");
      cleaned = cleaned.replace(/^(\s*)[-*•]\s+/, "$1");
      cleaned = cleaned.replace(/^(\s*)\|\s*/, "$1");
      cleaned = cleaned.replace(/\t/g, "  ");

      const match = cleaned.match(/^(\s*)(.*?)(\s*\([^)]*\)\s*)?$/);
      if (match && match[2]) {
        const indent = match[1] || "";
        const text = match[2];
        const suffix = match[3] || "";
        if (!text.includes("<br/>") && text.length > 25) {
          const wrapped = wrapText(text);
          cleaned = indent + wrapped + suffix;
        }
      }
      return cleaned;
    })
    .join("\n");
  content = content.replace(/root\s*\(\(\s*(.*?)\s*\)\)/, (match, label) => {
    const wrappedLabel = wrapText(label, 30);
    return `root((${wrappedLabel}))`;
  });

  const lines = content.split("\n");
  const topLevel = lines.filter((ln) => /^ {2}[^ ]/.test(ln));
  const hasExplicitRoot = topLevel.some((ln) => /root\s*\(\(/.test(ln));

  if (!hasExplicitRoot || topLevel.length > 1) {
    const body = lines
      .filter((ln, idx) => !(idx === 0 && ln.startsWith("mindmap")))
      .map((ln) => "    " + ln.trim());

    const wrapped = ["mindmap", "  root((Auto Root))", ...body];

    return wrapped.join("\n").trim();
  }

  const rootLine = topLevel.find((l) => /root\s*\(\(/.test(l));

  if (!rootLine) {
    content =
      "mindmap\n  root((Auto Root))\n" +
      lines
        .slice(1)
        .map((l) => "    " + l.trim())
        .join("\n");
  } else {
    const rootIndent = rootLine.match(/^(\s*)/)?.[1] || "  ";
    const childIndent = rootIndent + "  ";
    const fixedLines: string[] = [];

    for (const ln of lines) {
      if (/^ {2}root/.test(ln)) {
        fixedLines.push(ln);
        continue;
      }
      if (/^ {2}[^ ]/.test(ln)) {
        fixedLines.push(childIndent + ln.trim());
      } else {
        fixedLines.push(ln);
      }
    }

    content = fixedLines.join("\n");
  }
  return content.trim();
};
const MindMapTab: React.FC = () => {
  const { t } = useTranslation();
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

        if (/Syntax error/i.test(svg) || /mermaid version/i.test(svg)) {
          throw new Error("Mermaid syntax error");
        }

        mermaidRef.current!.innerHTML = svg;
        dispatch(setSVG(svg));

        if (startTimeRef.current) {
          dispatch(setGenerationTime(performance.now() - startTimeRef.current));
        }

        dispatch(setRendered(true));
      } catch (error: any) {
        console.error("❌ Mermaid render error:", error);

        dispatch(setError("Mindmap rendering failed"));
        dispatch(setRendered(true));

        mermaidRef.current!.innerHTML = `
          <div class="mermaid-error">
            ⚠️ ${t("mindmap.invalidFormat") || "Invalid mindmap format"}
          </div>
        `;

        window.dispatchEvent(
          new CustomEvent("global-error", {
            detail: {
              message: "Failed to render MindMap: Invalid format",
              type: "error",
            },
          })
        );
      }
    };

    renderMermaid();
  }, [finalText, dispatch, isRendered, t]);

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
          throw new Error("Empty mindmap returned");
        }
      } catch (err: any) {
        console.error("❌ Mindmap fetch error:", err);
        dispatch(setError(err.message || "Mindmap generation failed"));
        dispatch(uiMindmapFailed());

        if (mermaidRef.current) {
          mermaidRef.current.innerHTML = `
            <div class="mermaid-error">
              ⚠️ Failed to generate mindmap: ${err.message}
            </div>
          `;
        }
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
