import React from "react";
import ReactMarkdown from "react-markdown";
import { useTranslation } from "react-i18next";
import "../../assets/css/AISummaryTab.css";
import { useAppSelector } from "../../redux/hooks";

// Renders the summary the pipeline streams into the store (see
// redux/useAudioPipeline). The stream is not owned here — this tab is unmounted
// whenever another tab is selected.
const AISummaryTab: React.FC = () => {
  const { t } = useTranslation();
  const { streamingText, finalText, progress, boardOcrPartial } = useAppSelector(s => s.summary);
  const typed = finalText ?? streamingText;

  // Each stage counts its own units, so they cannot share one label: a fold
  // restarts the numbering, and reduce has nothing to count at all.
  const progressLabel = (p: { stage: string; chunk: number; chunks: number }) => {
    if (p.stage === "reduce") {
      return t("tabs.summaryProgressReduce", {
        defaultValue: "Writing the summary…",
      });
    }
    const key = p.stage === "fold" ? "tabs.summaryProgressFold" : "tabs.summaryProgress";
    return t(key, {
      current: p.chunk,
      total: p.chunks,
      defaultValue: p.stage === "fold"
        ? "Merging notes {{current}} of {{total}}…"
        : "Analyzing part {{current}} of {{total}}…",
    });
  };

  return (
    <div className="summary-tab">
      {boardOcrPartial && (
        <div className="summary-board-warning" role="status">
          {t("summary.boardOcrPartial")}
        </div>
      )}
      {progress && !typed && (
        <div className="summary-progress">
          {progressLabel(progress).replace(/(?:\u2026|\.{3})\s*$/, "")}
          <span className="summary-progress-dots" aria-hidden="true">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
        </div>
      )}
      {typed && (
        <div className="summary-content">
          <ReactMarkdown>{typed}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};

export default AISummaryTab;