import React, { useState, useMemo, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import "../../assets/css/ResultSection.css";
import searchIcon from "../../assets/images/search-icon.svg";
import { formatSecondsToTime } from "../../utils/timeUtils";
import { csDownloadUrl, extractFileKey } from "../../services/api";
import { useTitleBarTheme } from "../../hooks/useTitleBarTheme";

// Content Search API types
export interface CsSearchParams {
  query?: string;
  image_base64?: string;
  max_num_results?: number;
  filter?: Record<string, string[]>;
}

export interface CsSearchResultMeta {
  file_name?: string;
  file_path?: string;
  type?: string;
  video_pin_second?: number;
  video_start_second?: number;
  video_end_second?: number;
  summary_text?: string;
  chunk_text?: string;
  doc_page_number?: number;
  tags?: string[];
  doc_filetype?: string;
}

export interface CsSearchResult {
  id: string;
  distance: number;
  meta: CsSearchResultMeta;
  score: number;
}

export type SearchResult = CsSearchResult;

type ResultTab = "all" | "document" | "image" | "video";
type ScoreFormat = "percent" | "decimal";

interface ResultSectionProps {
  results: SearchResult[];
  error?: string | null;
}

function getFileName(result: SearchResult): string {
  const meta = result?.meta;
  if (!meta) return "Unknown";
  if (meta.file_name) return meta.file_name;
  if (meta.file_path) return meta.file_path.split("/").pop() || "Unknown";
  return "Unknown";
}

function fileExtension(name: string): string {
  const lower = (name || "").toLowerCase();
  if (!lower.includes(".")) return "";
  return lower.slice(lower.lastIndexOf("."));
}

function formatScore(score: number, fmt: ScoreFormat = "percent"): string {
  if (fmt === "decimal") return (score / 100).toFixed(2);
  if (score <= 0) return "0%";
  if (score < 1) return "< 1%";
  return `${Math.round(score)}%`;
}

/** Inline URL for a result's file, or null when it has no resolvable path. */
function resultUrls(meta: CsSearchResultMeta) {
  const fileKey = meta.file_path ? extractFileKey(meta.file_path) : null;
  return {
    downloadUrl: fileKey ? csDownloadUrl(fileKey) : null,
    inlineUrl: fileKey ? csDownloadUrl(fileKey, true) : null,
  };
}

// ── Video Thumbnail ──────────────────────────────────────────
// Grabs a single frame at the matched timestamp by seeking an off-screen
// <video> and painting it to a canvas.

const VideoThumbnail: React.FC<{ url: string; seekTime: number }> = ({ url, seekTime }) => {
  const imgRef = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    const video = document.createElement("video");
    video.muted = true;
    video.preload = "auto";

    const cleanup = () => {
      video.removeAttribute("src");
      video.load();
    };

    const captureFrame = () => {
      try {
        const canvas = document.createElement("canvas");
        const w = video.videoWidth;
        const h = video.videoHeight;
        if (!w || !h) return;
        const maxW = 300;
        const scale = Math.min(1, maxW / w);
        canvas.width = Math.round(w * scale);
        canvas.height = Math.round(h * scale);
        canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
        if (active && imgRef.current) {
          imgRef.current.src = canvas.toDataURL("image/jpeg", 0.75);
          setLoaded(true);
        }
      } catch (e) {
        console.warn("Video thumbnail capture failed:", e);
      }
      cleanup();
    };

    const doSeek = () => {
      const target = Math.max(0, Math.min(seekTime || 1, video.duration - 0.1));
      video.currentTime = target;
    };

    video.addEventListener("seeked", captureFrame);
    video.addEventListener("error", cleanup);
    video.addEventListener("loadedmetadata", doSeek);

    const timer = setTimeout(() => {
      if (active && !loaded) cleanup();
    }, 10000);

    // Cache-bust so each thumbnail instance seeks its own copy
    const separator = url.includes("?") ? "&" : "?";
    video.src = `${url}${separator}_thumb=${seekTime}`;

    return () => {
      active = false;
      clearTimeout(timer);
      cleanup();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, seekTime]);

  return (
    <>
      <img ref={imgRef} className={`cs-thumb-img ${loaded ? "" : "cs-thumb-hidden"}`} alt="" />
      {!loaded && <div className="cs-thumb-shimmer" />}
    </>
  );
};

// ── PDF Thumbnail ────────────────────────────────────────────
// pdfjs is imported lazily so it only loads for results that need it.

const PdfThumbnail: React.FC<{ url: string; pageNum: number }> = ({ url, pageNum }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      if (!cancelled && !loaded) {
        cancelled = true;
        setFailed(true);
      }
    }, 60000);

    (async () => {
      try {
        const pdfjsLib = await import("pdfjs-dist");
        pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
          "pdfjs-dist/build/pdf.worker.min.mjs",
          import.meta.url
        ).href;

        const pdf = await pdfjsLib.getDocument({ url }).promise;
        if (cancelled) return;
        const safePage = Math.min(Math.max(1, pageNum), pdf.numPages);
        const page = await pdf.getPage(safePage);
        const vp = page.getViewport({ scale: 1 });
        // Render above the CSS display size (and for HiDPI) so the canvas is
        // only ever downscaled on screen, never upscaled and blurred.
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const scaled = page.getViewport({ scale: (300 / vp.width) * dpr });

        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;
        canvas.width = scaled.width;
        canvas.height = scaled.height;
        const ctx = canvas.getContext("2d");
        if (ctx) await page.render({ canvas, canvasContext: ctx, viewport: scaled }).promise;
        if (!cancelled) {
          clearTimeout(timer);
          setLoaded(true);
        }
      } catch (err) {
        console.warn("PDF thumbnail failed:", err);
        if (!cancelled) setFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, pageNum]);

  if (failed) return <FileTypeBadge filename="document.pdf" />;

  return (
    <>
      <canvas ref={canvasRef} className={`cs-thumb-canvas ${loaded ? "" : "cs-thumb-hidden"}`} />
      {!loaded && <div className="cs-thumb-shimmer" />}
    </>
  );
};

// ── File Type Badge ──────────────────────────────────────────

const FILE_TYPE_PALETTE: Record<string, { bg: string; color: string; label: string }> = {
  PDF: { bg: "#fee2e2", color: "#dc2626", label: "PDF" },
  DOCX: { bg: "#dbeafe", color: "#2563eb", label: "DOC" },
  DOC: { bg: "#dbeafe", color: "#2563eb", label: "DOC" },
  PPTX: { bg: "#fef3c7", color: "#d97706", label: "PPT" },
  PPT: { bg: "#fef3c7", color: "#d97706", label: "PPT" },
  XLSX: { bg: "#d1fae5", color: "#059669", label: "XLS" },
  XLS: { bg: "#d1fae5", color: "#059669", label: "XLS" },
  CSV: { bg: "#d1fae5", color: "#059669", label: "CSV" },
  TXT: { bg: "#f3f4f6", color: "#6b7280", label: "TXT" },
  HTML: { bg: "#fce7f3", color: "#db2777", label: "HTML" },
  MD: { bg: "#f3f4f6", color: "#6b7280", label: "MD" },
  JPG: { bg: "#ecfdf5", color: "#059669", label: "IMG" },
  JPEG: { bg: "#ecfdf5", color: "#059669", label: "IMG" },
  PNG: { bg: "#ecfdf5", color: "#059669", label: "IMG" },
  MP4: { bg: "#ede9fe", color: "#7c3aed", label: "VIDEO" },
};

const FileTypeBadge: React.FC<{ filename: string }> = ({ filename }) => {
  const ext = fileExtension(filename).replace(".", "").toUpperCase();
  const info = FILE_TYPE_PALETTE[ext] || { bg: "#f3f4f6", color: "#6b7280", label: ext || "FILE" };
  return (
    <div className="cs-thumb-badge" style={{ background: info.bg, color: info.color }}>
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
      <span className="cs-thumb-badge-label">{info.label}</span>
    </div>
  );
};

// ── Preview Modal ────────────────────────────────────────────

const PreviewModal: React.FC<{ result: SearchResult; onClose: () => void }> = ({
  result,
  onClose,
}) => {
  const { t } = useTranslation();
  useTitleBarTheme(true, 'dimmed');
  const meta = result?.meta || {};
  const fileName = meta.file_name || getFileName(result);
  const fileType = meta.type;
  const { downloadUrl, inlineUrl } = resultUrls(meta);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  // Jump straight to the matched moment, then play.
  const handleVideoReady = () => {
    const video = videoRef.current;
    if (!video) return;
    const seekTo = meta.video_start_second ?? meta.video_pin_second;
    if (seekTo != null && seekTo > 0) {
      const onSeeked = () => {
        video.removeEventListener("seeked", onSeeked);
        video.play().catch(() => {});
      };
      video.addEventListener("seeked", onSeeked);
      video.currentTime = seekTo;
    } else {
      video.play().catch(() => {});
    }
  };

  const renderContent = () => {
    if (!downloadUrl) return <p className="cs-preview-empty">{t("resultSection.previewUnavailable")}</p>;

    if (fileType === "video") {
      return (
        <video
          ref={videoRef}
          className="cs-preview-video"
          controls
          preload="auto"
          src={inlineUrl!}
          onLoadedData={handleVideoReady}
        />
      );
    }

    if (fileType === "image") {
      return <img className="cs-preview-image" src={inlineUrl!} alt={fileName} />;
    }

    if (fileType === "document" && meta.doc_filetype?.includes("pdf")) {
      const page = meta.doc_page_number;
      return (
        <iframe
          className="cs-preview-pdf"
          src={page ? `${inlineUrl!}#page=${page}` : inlineUrl!}
          title={fileName}
        />
      );
    }

    if (meta.summary_text || meta.chunk_text) {
      return <pre className="cs-preview-text">{meta.summary_text || meta.chunk_text}</pre>;
    }

    return (
      <div className="cs-preview-download">
        <p>{t("resultSection.previewUnavailableType")}</p>
        <a href={downloadUrl} download>
          {t("resultSection.download", { name: fileName })}
        </a>
      </div>
    );
  };

  return (
    <div className="cs-preview-overlay" onClick={onClose}>
      <div className="cs-preview-modal" onClick={(e) => e.stopPropagation()}>
        <div className="cs-preview-header">
          <h3 className="cs-preview-title" title={fileName}>
            {fileName}
          </h3>
          <button
            className="cs-preview-close"
            onClick={onClose}
            aria-label={t("resultSection.closePreview")}
          >
            &times;
          </button>
        </div>

        <div className="cs-preview-info-bar">
          <span>
            {t("resultSection.type")} {fileType}
          </span>
          <span>
            {t("resultSection.score")}: {formatScore(result?.score ?? 0)}
          </span>
          {fileType === "video" && meta.video_start_second != null && meta.video_end_second != null && (
            <span>
              {t("resultSection.time")} {formatSecondsToTime(meta.video_start_second)} -{" "}
              {formatSecondsToTime(meta.video_end_second)}
            </span>
          )}
          {fileType === "document" && meta.doc_page_number != null && (
            <span>
              {t("resultSection.page")}: {meta.doc_page_number}
            </span>
          )}
        </div>

        <div className="cs-preview-body">{renderContent()}</div>
      </div>
    </div>
  );
};

// ── Result Card ──────────────────────────────────────────────

const ResultCard: React.FC<{
  result: SearchResult;
  scoreFormat: ScoreFormat;
  onPreview: () => void;
}> = ({ result, scoreFormat, onPreview }) => {
  const { t } = useTranslation();
  const [imageError, setImageError] = useState(false);
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const meta = result?.meta || {};
  const fileName = meta.file_name || getFileName(result);
  const tags = Array.isArray(meta.tags) ? meta.tags : [];
  const fileType = meta.type;
  const { downloadUrl } = resultUrls(meta);
  const isIndependentText = !meta.file_name && fileType === "document";

  const renderThumbnail = () => {
    if (fileType === "image" && downloadUrl && !imageError) {
      return (
        <img
          src={downloadUrl}
          alt={fileName}
          className="cs-thumb-img"
          loading="lazy"
          onError={() => setImageError(true)}
        />
      );
    }

    if (fileType === "video" && downloadUrl) {
      return (
        <>
          <VideoThumbnail url={downloadUrl} seekTime={meta.video_pin_second || 0} />
          <div className="cs-thumb-play">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="white">
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
          {meta.video_pin_second != null && (
            <span className="cs-thumb-time">{formatSecondsToTime(meta.video_pin_second)}</span>
          )}
        </>
      );
    }

    if (fileType === "document" && meta.doc_filetype?.includes("pdf") && downloadUrl) {
      return <PdfThumbnail url={downloadUrl} pageNum={meta.doc_page_number || 1} />;
    }

    return <FileTypeBadge filename={fileName} />;
  };

  // Expandable body text — kept from the existing card so long summaries and
  // raw-text results stay readable inside the list.
  const renderExpandableText = (label: string, text: string) => (
    <div className="cs-result-item-summary">
      <p
        className={`cs-result-item-summary-text${
          summaryExpanded ? " cs-result-item-summary-text--expanded" : ""
        }`}
      >
        <span className="cs-result-item-summary-label">{label}: </span>
        {text}
      </p>
      <button
        className="cs-result-item-summary-toggle"
        onClick={(e) => {
          e.stopPropagation();
          setSummaryExpanded((prev) => !prev);
        }}
      >
        {summaryExpanded ? t("resultSection.showLess") : t("resultSection.showMore")}
      </button>
    </div>
  );

  return (
    <div className="cs-result-item cs-result-item--clickable" onClick={onPreview}>
      <div className="cs-result-item-preview">{renderThumbnail()}</div>

      <div className="cs-result-item-content">
        {isIndependentText ? (
          renderExpandableText("Raw Text", meta.chunk_text ?? "")
        ) : (
          <>
            <div className="cs-result-item-row">
              <span className="cs-result-item-value" title={fileName}>
                {fileName}
              </span>
            </div>

            {fileType === "document" && (
              <div className="cs-result-item-row">
                <span className="cs-result-item-page-label">
                  {t("resultSection.page")}: {meta.doc_page_number ?? "NA"}
                </span>
              </div>
            )}

            {fileType === "document" && meta.chunk_text && renderExpandableText("Raw Text", meta.chunk_text)}
          </>
        )}

        {fileType === "video" && (
          <div className="cs-result-item-row">
            <span className="cs-result-item-page-label">
              {t("resultSection.time")} {formatSecondsToTime(meta.video_pin_second)}
            </span>
          </div>
        )}

        {fileType === "video" &&
          meta.summary_text &&
          renderExpandableText(t("resultSection.summarization"), meta.summary_text)}

        {tags.length > 0 && (
          <div className="cs-result-item-row">
            <span className="cs-result-item-label">{t("resultSection.labels")}:</span>
            <div className="cs-result-item-tags">
              {tags.map((tag) => (
                <span key={tag} className="cs-result-item-tag">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="cs-result-item-score-section">
        <span className="cs-result-item-score-box">
          {t("resultSection.score")}: {formatScore(result?.score ?? 0, scoreFormat)}
        </span>
      </div>
    </div>
  );
};

// ── Result Section ───────────────────────────────────────────

/** Render the canonical percent threshold in the currently selected unit. */
function minScoreToText(pct: number, fmt: ScoreFormat): string {
  return fmt === "decimal" ? (pct / 100).toFixed(2) : String(Math.round(pct));
}

const ResultSection: React.FC<ResultSectionProps> = ({ results, error }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<ResultTab>("all");
  const [scoreFormat, setScoreFormat] = useState<ScoreFormat>("percent");
  // `minScore` is canonical and always in percent (matching result.score);
  // `minScoreText` is the raw box contents so it can be cleared while typing
  // without a value being forced back in.
  const [minScore, setMinScore] = useState(0);
  const [minScoreText, setMinScoreText] = useState("0");
  const [previewResult, setPreviewResult] = useState<SearchResult | null>(null);

  const isDecimalScore = scoreFormat === "decimal";

  const handleMinScoreChange = (raw: string) => {
    setMinScoreText(raw);
    if (raw.trim() === "") {
      setMinScore(0); // empty box = no threshold while editing
      return;
    }
    const parsed = Number(raw);
    if (Number.isNaN(parsed)) return;
    const asPercent = isDecimalScore ? parsed * 100 : parsed;
    setMinScore(Math.max(0, Math.min(100, asPercent)));
  };

  // Normalize on blur so the box always ends up showing the clamped value.
  const handleMinScoreBlur = () => setMinScoreText(minScoreToText(minScore, scoreFormat));

  // Switching units converts the displayed threshold (60 <-> 0.60).
  const handleScoreFormatChange = (fmt: ScoreFormat) => {
    setScoreFormat(fmt);
    setMinScoreText(minScoreToText(minScore, fmt));
  };

  const safeResults = Array.isArray(results) ? results : [];

  const filteredResults = useMemo(() => {
    const filtered =
      activeTab === "all" ? safeResults : safeResults.filter((r) => r?.meta?.type === activeTab);
    return [...filtered]
      .filter((r) => (r?.score ?? 0) >= minScore)
      .sort((a, b) => (b?.score ?? 0) - (a?.score ?? 0));
  }, [safeResults, activeTab, minScore]);

  return (
    <div className="cs-result-card">
      <div className="cs-result-header">
        <span className="cs-result-title">{t("resultSection.title")}</span>
        <div className="cs-result-score-format">
          <span className="cs-result-score-format-label">{t("resultSection.minScore")}</span>
          <input
            className="cs-result-min-score-input"
            type="number"
            min={0}
            max={isDecimalScore ? 1 : 100}
            step={isDecimalScore ? 0.01 : 1}
            value={minScoreText}
            onChange={(e) => handleMinScoreChange(e.target.value)}
            onBlur={handleMinScoreBlur}
          />
          <span className="cs-result-score-format-label">{t("resultSection.scoreFormat")}</span>
          <select
            className="cs-result-score-format-select"
            value={scoreFormat}
            onChange={(e) => handleScoreFormatChange(e.target.value as ScoreFormat)}
          >
            <option value="percent">%</option>
            <option value="decimal">0-1</option>
          </select>
        </div>
      </div>
      <div className="cs-result-subtitle">{t("resultSection.subtitle")}</div>
      <div className="cs-result-tabs">
        <button
          className={`cs-result-tab ${activeTab === "all" ? "cs-result-tab--active" : ""}`}
          onClick={() => setActiveTab("all")}
        >
          {t("resultSection.all")}
        </button>
        <button
          className={`cs-result-tab ${activeTab === "document" ? "cs-result-tab--active" : ""}`}
          onClick={() => setActiveTab("document")}
        >
          {t("resultSection.documents")}
        </button>
        <button
          className={`cs-result-tab ${activeTab === "image" ? "cs-result-tab--active" : ""}`}
          onClick={() => setActiveTab("image")}
        >
          {t("resultSection.images")}
        </button>
        <button
          className={`cs-result-tab ${activeTab === "video" ? "cs-result-tab--active" : ""}`}
          onClick={() => setActiveTab("video")}
        >
          {t("resultSection.videos")}
        </button>
      </div>

      <div className="cs-result-grid">
        {error ? (
          <div className="cs-result-empty cs-result-error">
            <span className="cs-result-error-title">{t("resultSection.backendUnavailable")}</span>
            <span className="cs-result-empty-hint">{t("resultSection.backendUnavailableHint")}</span>
          </div>
        ) : filteredResults.length === 0 ? (
          <div className="cs-result-empty">
            <img
              src={searchIcon}
              alt="search"
              className="cs-result-empty-icon"
              width="48"
              height="48"
            />
            <span className="cs-result-empty-title">{t("resultSection.noResults")}</span>
            <span className="cs-result-empty-hint">{t("resultSection.noResultsHint")}</span>
          </div>
        ) : (
          filteredResults.map((result, index) => (
            <ResultCard
              key={result?.id || index}
              result={result}
              scoreFormat={scoreFormat}
              onPreview={() => setPreviewResult(result)}
            />
          ))
        )}
      </div>

      {/* Portalled to <body> so the overlay escapes any ancestor stacking
          context and layers above the sticky content-search subheader. */}
      {previewResult &&
        createPortal(
          <PreviewModal result={previewResult} onClose={() => setPreviewResult(null)} />,
          document.body
        )}
    </div>
  );
};

export default ResultSection;
