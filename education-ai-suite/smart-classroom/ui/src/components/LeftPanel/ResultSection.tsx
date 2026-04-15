import React, { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/ResultSection.css";
import searchIcon from "../../assets/images/search-icon.svg";
import folderIcon from "../../assets/images/folder.svg";
import streamingIcon from "../../assets/images/streamingIcon.svg";
import cameraIcon from "../../assets/images/camera-icon.svg";
import { formatSecondsToTime } from "../../utils/timeUtils";

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

interface ResultSectionProps {
  results: SearchResult[];
}

function getFileName(result: SearchResult): string {
  const meta = result?.meta;
  if (!meta) return "Unknown";
  if (meta.file_name) return meta.file_name;
  if (meta.file_path) return meta.file_path.split("/").pop() || "Unknown";
  return "Unknown";
}

const ResultSection: React.FC<ResultSectionProps> = ({ results }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<ResultTab>("all");

  const safeResults = Array.isArray(results) ? results : [];
  console.log("ResultSection received:", safeResults.length, "results", safeResults);

  const filteredResults = useMemo(() => {
    const filtered = activeTab === "all" 
      ? safeResults 
      : safeResults.filter((r) => r?.meta?.type === activeTab);
    return [...filtered].sort((a, b) => (b?.score ?? 0) - (a?.score ?? 0));
  }, [safeResults, activeTab]);

  return (
    <div className="cs-result-card">
      <div className="cs-result-header">
        <span className="cs-result-title">{t("resultSection.title")}</span>
      </div>
      <div className="cs-result-subtitle">
        {t("resultSection.subtitle")}
      </div>
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
        {filteredResults.length === 0 ? (
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
            <ResultCard key={result?.id || index} result={result} />
          ))
        )}
      </div>
    </div>
  );
};

const ResultCard: React.FC<{ result: SearchResult }> = ({ result }) => {
  const { t } = useTranslation();
  const [imageError, setImageError] = useState(false);
  const meta = result?.meta || {};
  const fileName = meta.file_name || getFileName(result);
  const tags = Array.isArray(meta.tags) ? meta.tags : [];
  const fileType = meta.type;
  const filePath = meta.file_path;

  const renderPreview = () => {
    // For image type with valid file path, try to show the image
    if (fileType === "image" && filePath && !imageError) {
      return (
        <img
          src={filePath}
          alt={fileName}
          className="cs-result-item-thumbnail"
          onError={() => setImageError(true)}
        />
      );
    }

    // Show type-specific placeholder icons
    if (fileType === "document") {
      return <img src={folderIcon} alt="document" className="cs-result-item-type-icon" />;
    }
    if (fileType === "video") {
      return <img src={streamingIcon} alt="video" className="cs-result-item-type-icon" />;
    }
    if (fileType === "image") {
      return <img src={cameraIcon} alt="image" className="cs-result-item-type-icon" />;
    }

    return null;
  };

  return (
    <div className="cs-result-item">
      {/* Section 1: Image/Preview (25%) */}
      <div className="cs-result-item-preview">
        {renderPreview()}
      </div>

      <div className="cs-result-item-content">
        <div className="cs-result-item-row">
          <span className="cs-result-item-value" title={fileName}>{fileName}</span>
        </div>

        {fileType === "document" && (
          <div className="cs-result-item-row">
            <span className="cs-result-item-page-label">Page: {meta.doc_page_number ?? "NA"}</span>
          </div>
        )}

        {fileType === "video" && (
          <div className="cs-result-item-row">
            <span className="cs-result-item-page-label">Time: {formatSecondsToTime(meta.video_pin_second)}</span>
          </div>
        )}

        {tags.length > 0 && (
          <div className="cs-result-item-row">
            <span className="cs-result-item-label">{t("resultSection.labels")}:</span>
            <div className="cs-result-item-tags">
              {tags.map((tag) => (
                <span key={tag} className="cs-result-item-tag">{tag}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="cs-result-item-score-section">
        <span className="cs-result-item-score-box">
          Score: {result?.score ?? 0}%
        </span>
      </div>
    </div>
  );
};

export default ResultSection;
