import React, { useRef, useState, useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/SearchSection.css";
import { csSearch } from "../../services/api";
import ResultSection, { type CsSearchResult } from "./ResultSection";
import warningIcon from "../../assets/images/warning-info.svg";
import cameraIcon from "../../assets/images/camera-icon.svg";
import noSearchIcon from "../../assets/images/no-search-icon.svg";
import { useAppSelector } from "../../redux/hooks";

type SearchTab = "text" | "image";
type SearchType = "document" | "image" | "video";

const MAX_QUERY_LENGTH = 100;
const DEFAULT_MAX_RESULTS = 10;

const ALLOWED_IMAGE_EXTENSIONS = new Set([".png"]);

function isAllowedImage(filename: string): boolean {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  return ALLOWED_IMAGE_EXTENSIONS.has(ext);
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1];
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

const SearchSection: React.FC = () => {
  const { t } = useTranslation();
  const csUploadsComplete = useAppSelector((s) => s.ui.csUploadsComplete);
  const csHasUploads = useAppSelector((s) => s.ui.csHasUploads);
  const csProcessing = useAppSelector((s) => s.ui.csProcessing);
  const csTags = useAppSelector((s) => s.ui.csTags);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const filterBoxRef = useRef<HTMLDivElement>(null);

  const [activeTab, setActiveTab] = useState<SearchTab>("text");

  const [query, setQuery] = useState("");

  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const [selectedTypes, setSelectedTypes] = useState<Set<SearchType>>(
    new Set(["document", "image", "video"])
  );

  const [isExpanded, setIsExpanded] = useState(true);

  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
  const [isLabelDropdownOpen, setIsLabelDropdownOpen] = useState(false);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (filterBoxRef.current && !filterBoxRef.current.contains(event.target as Node)) {
        setIsLabelDropdownOpen(false);
      }
    };

    if (isLabelDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isLabelDropdownOpen]);

  // Reset search when all uploads are cleared
  useEffect(() => {
    if (!csHasUploads) {
      setQuery("");
      setImageFile(null);
      if (imagePreview) {
        URL.revokeObjectURL(imagePreview);
      }
      setImagePreview(null);
      setSelectedTypes(new Set(["document", "image", "video"]));
      setSelectedLabels([]);
      setMaxResults(DEFAULT_MAX_RESULTS);
      setSearchResults([]);
      setShowResults(false);
      setHasSearched(false);
      setActiveTab("text");
    }
  }, [csHasUploads]);

  // Remove selected labels that are no longer available
  useEffect(() => {
    setSelectedLabels((prev) => prev.filter((label) => csTags.includes(label)));
  }, [csTags]);

  const [maxResults, setMaxResults] = useState<number>(DEFAULT_MAX_RESULTS);

  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<CsSearchResult[]>([]);
  const [showResults, setShowResults] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const hasValidInput = activeTab === "text" ? query.trim().length > 0 : imageFile !== null;
  const hasSelectedType = selectedTypes.size > 0;
  const canSearch = hasValidInput && hasSelectedType && !isSearching;

  const handleTabChange = useCallback((tab: SearchTab) => {
    setActiveTab(tab);
    if (tab === "image") {
      setSelectedTypes((prev) => {
        const next = new Set(prev);
        next.delete("document");
        if (next.size === 0) {
          next.add("image");
          next.add("video");
        }
        return next;
      });
    } else {
      setSelectedTypes(new Set(["document", "image", "video"]));
    }
  }, []);

  const toggleType = useCallback((type: SearchType) => {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }, []);

  const toggleLabel = useCallback((label: string) => {
    setSelectedLabels((prev) => {
      if (prev.includes(label)) {
        return prev.filter((l) => l !== label);
      }
      return [...prev, label];
    });
  }, []);

  const removeLabel = useCallback((label: string) => {
    setSelectedLabels((prev) => prev.filter((l) => l !== label));
  }, []);

  const handleImageDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleImageDragLeave = () => setIsDragOver(false);

  const handleImageDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files).filter((f) => isAllowedImage(f.name));
    if (files.length > 0) {
      processImageFile(files[0]);
    }
  };

  const handleImageBrowse = () => imageInputRef.current?.click();

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []).filter((f) => isAllowedImage(f.name));
    if (files.length > 0) {
      processImageFile(files[0]);
    }
    if (imageInputRef.current) imageInputRef.current.value = "";
  };

  const processImageFile = (file: File) => {
    setImageFile(file);
    const url = URL.createObjectURL(file);
    setImagePreview(url);
  };

  const clearImage = () => {
    setImageFile(null);
    if (imagePreview) {
      URL.revokeObjectURL(imagePreview);
    }
    setImagePreview(null);
  };

  // Search handler
  const handleSearch = async () => {
    if (!canSearch) return;

    setIsSearching(true);
    setHasSearched(true);

    try {
      const filter: Record<string, string[]> = {};
      if (selectedTypes.size > 0) {
        filter.type = Array.from(selectedTypes);
      }
      if (selectedLabels.length > 0) {
        filter.tags = selectedLabels;
      }
      let results: CsSearchResult[];
      if (activeTab === "text") {
        results = await csSearch({
          query: query.trim(),
          max_num_results: maxResults,
          filter: Object.keys(filter).length > 0 ? filter : undefined,
        });
      } else {
        const base64 = await fileToBase64(imageFile!);
        results = await csSearch({
          image_base64: base64,
          max_num_results: maxResults,
          filter: Object.keys(filter).length > 0 ? filter : undefined,
        });
      }
      setSearchResults(results);
      setShowResults(true);
    } catch (error) {
      console.error("Search failed:", error);
      setSearchResults([]);
      setShowResults(true);
    } finally {
      setIsSearching(false);
    }
  };

  // Reset handler
  const handleReset = () => {
    setQuery("");
    clearImage();
    setSelectedTypes(new Set(["document", "image", "video"]));
    setSelectedLabels([]);
    setMaxResults(DEFAULT_MAX_RESULTS);
    setSearchResults([]);
    setShowResults(false);
    setHasSearched(false);
    setActiveTab("text");
  };

  return (
    <>
      <div className="cs-search-card">
        {/* Header */}
        <div className="cs-search-header">
          <span className="cs-search-title">{t("searchSection.title")}</span>
          <button 
            className={`cs-search-chevron ${isExpanded ? "cs-search-chevron--expanded" : ""}`}
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? "Collapse" : "Expand"}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 6L8 10L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        {/* Processing warning when some files are still processing but search is available */}
        {csUploadsComplete && csProcessing && (
          <div className="cs-search-warning-frame">
            <svg className="cs-search-warning-frame-icon" width="15" height="15" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M8 1C4.13438 1 1 4.13438 1 8C1 11.8656 4.13438 15 8 15C11.8656 15 15 11.8656 15 8C15 4.13438 11.8656 1 8 1ZM8 11.5C7.58579 11.5 7.25 11.1642 7.25 10.75C7.25 10.3358 7.58579 10 8 10C8.41421 10 8.75 10.3358 8.75 10.75C8.75 11.1642 8.41421 11.5 8 11.5ZM8.75 8.5C8.75 8.91421 8.41421 9.25 8 9.25C7.58579 9.25 7.25 8.91421 7.25 8.5V5C7.25 4.58579 7.58579 4.25 8 4.25C8.41421 4.25 8.75 4.58579 8.75 5V8.5Z" fill="white"/>
            </svg>
            <span className="cs-search-warning-frame-text">Some files are still processing. You can search now; results may expand once processing finishes.</span>
          </div>
        )}

        {isExpanded && (
          <>
          {!csHasUploads ? (
          /* No files uploaded */
          <div className="cs-search-disabled">
            <img 
              src={noSearchIcon} 
              alt="search unavailable" 
              className="cs-search-disabled-icon"
            />
            <span className="cs-search-disabled-title">{t("searchSection.searchNotAvailable")}</span>
            <span className="cs-search-disabled-hint">{t("searchSection.uploadFilesToEnable")}</span>
          </div>
        ) : !csUploadsComplete ? (
          /* Files uploading but none completed yet */
          <div className="cs-search-disabled">
            <img 
              src={noSearchIcon} 
              alt="search unavailable" 
              className="cs-search-disabled-icon"
            />
            <span className="cs-search-disabled-title">{t("searchSection.searchNotAvailable")}</span>
            <span className="cs-search-disabled-hint">{t("searchSection.filesStillUploading")}</span>
          </div>
        ) : (
          /* Full search form when at least one upload is complete */
          <>
            <div className="cs-search-tabs">
              <button
                className={`cs-search-tab ${activeTab === "text" ? "cs-search-tab--active" : ""}`}
                onClick={() => handleTabChange("text")}
              >
                {t("searchSection.textSearch")}
              </button>
              <button
                className={`cs-search-tab ${activeTab === "image" ? "cs-search-tab--active" : ""}`}
                onClick={() => handleTabChange("image")}
              >
                {t("searchSection.imageSearch")}
              </button>
            </div>

            {activeTab === "text" && (
              <div className="cs-search-content">
                <div className="cs-search-label-row">
                  <span className="cs-search-label">{t("searchSection.yourQuestion")}</span>
                  <span className="cs-search-char-count">
                    {query.length}/{MAX_QUERY_LENGTH}
                  </span>
                </div>
                <textarea
                  className="cs-search-textarea"
                  placeholder={t("searchSection.placeholder")}
                  value={query}
                  onChange={(e) => {
                    if (e.target.value.length <= MAX_QUERY_LENGTH) {
                      setQuery(e.target.value);
                    }
                  }}
                  maxLength={MAX_QUERY_LENGTH}
                />
              </div>
            )}

            {/* Image Search Content */}
            {activeTab === "image" && (
              <div className="cs-search-content">
                {!imageFile ? (
                  <div
                    className={`cs-search-dropzone ${isDragOver ? "cs-search-dropzone--active" : ""}`}
                    onDragOver={handleImageDragOver}
                    onDragLeave={handleImageDragLeave}
                    onDrop={handleImageDrop}
                    onClick={handleImageBrowse}
                  >
                    <img 
                      src={cameraIcon} 
                      alt="camera" 
                      className="cs-search-dropzone-camera"
                      width="56" 
                      height="48" 
                    />
                    <p className="cs-search-dropzone-text">
                      {t("searchSection.dragDropImage")}
                    </p>
                    <p className="cs-search-dropzone-hint">{t("searchSection.orClickBrowse")}</p>
                  </div>
                ) : (
                  <div className="cs-search-image-preview">
                    <img src={imagePreview!} alt="Search preview" />
                    <button className="cs-search-image-clear" onClick={clearImage}>
                      ✕
                    </button>
                  </div>
                )}
                <input
                  ref={imageInputRef}
                  type="file"
                  accept=".jpg"
                  style={{ display: "none" }}
                  onChange={handleImageChange}
                />
              </div>
            )}

            {/* Search Type Selection */}
            <div className="cs-search-type-section">
              <div className="cs-search-type-label">{t("searchSection.selectSearchType")}</div>
              <div className="cs-search-type-options">
                {activeTab === "text" && (
                  <label className="cs-search-type-option">
                    <input
                      type="checkbox"
                      checked={selectedTypes.has("document")}
                      onChange={() => toggleType("document")}
                    />
                    <span>{t("searchSection.documents")}</span>
                  </label>
                )}
                <label className="cs-search-type-option">
                  <input
                    type="checkbox"
                    checked={selectedTypes.has("image")}
                    onChange={() => toggleType("image")}
                  />
                  <span>{t("searchSection.images")}</span>
                </label>
                <label className="cs-search-type-option">
                  <input
                    type="checkbox"
                    checked={selectedTypes.has("video")}
                    onChange={() => toggleType("video")}
                  />
                  <span>{t("searchSection.videos")}</span>
                </label>
              </div>
              {!hasSelectedType && (
                <div className="cs-search-warning">
                  <span className="cs-search-warning-icon">
                    <img src={warningIcon} alt="warning" width="16" height="16" />
                  </span>
                  <span>{t("searchSection.selectAtLeastOneType")}</span>
                </div>
              )}
            </div>

            {/* Section Divider */}
            <div className="cs-search-divider" />

            {/* Filter by Label */}
            <div className={`cs-search-filter-section ${!hasSelectedType || !hasValidInput ? "cs-search-filter-disabled" : ""}`}>
              <div className="cs-search-filter-label">{t("searchSection.filterByLabel")}</div>
              <div 
                ref={filterBoxRef}
                className="cs-search-filter-box"
                onClick={() => hasSelectedType && hasValidInput && setIsLabelDropdownOpen(!isLabelDropdownOpen)}
              >
                <div className="cs-search-filter-chips">
                  {selectedLabels.map((label) => (
                    <span key={label} className="cs-search-chip">
                      {label}
                      <button
                        className="cs-search-chip-remove"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeLabel(label);
                        }}
                        disabled={!hasSelectedType || !hasValidInput}
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                </div>
                {isLabelDropdownOpen && hasSelectedType && hasValidInput && (
                  <div className="cs-search-filter-dropdown" onClick={(e) => e.stopPropagation()}>
                    {csTags.length === 0 ? (
                      <div className="cs-search-filter-dropdown-empty">No labels available</div>
                    ) : (
                      csTags.map((label) => (
                        <label key={label} className="cs-search-filter-dropdown-item">
                          <input
                            type="checkbox"
                            checked={selectedLabels.includes(label)}
                            onChange={() => toggleLabel(label)}
                          />
                          <span>{label}</span>
                        </label>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div> 

            {/* Top Results */}
            <div className={`cs-search-results-section ${!hasSelectedType || !hasValidInput ? "cs-search-filter-disabled" : ""}`}>
              <div className="cs-search-results-row">
                <span className="cs-search-results-label">{t("searchSection.topResults")}</span>
                <input
                  type="number"
                  className="cs-search-results-input"
                  value={maxResults}
                  onChange={(e) => setMaxResults(Math.max(1, parseInt(e.target.value) || 1))}
                  min={1}
                  max={1000}
                  disabled={!hasSelectedType || !hasValidInput}
                />
              </div>
            </div>

            {/* Action Buttons */}
            <div className="cs-search-actions">
              <button
                className={`cs-search-btn cs-search-btn--primary ${isSearching ? "cs-search-btn--loading" : ""}`}
                onClick={handleSearch}
                disabled={!canSearch}
              >
                {isSearching && <span className="cs-spinner" />}
                {isSearching ? t("searchSection.searching") : t("searchSection.search")}
              </button>
              <button
                className="cs-search-btn cs-search-btn--secondary"
                onClick={handleReset}
              >
                {t("searchSection.reset")}
              </button>
            </div>
            <div className="cs-search-divider" />

            {/* Results Section */}
            {hasSearched && showResults && (
              <ResultSection results={searchResults} />
            )}
          </>
        )}
        </>
        )}
      </div>
    </>
  );
};

export default SearchSection;
