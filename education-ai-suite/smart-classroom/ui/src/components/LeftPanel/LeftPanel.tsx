import { useState, useEffect } from "react";
import TranscriptsTab from "../Tabs/TranscriptsTab";
import AISummaryTab from "../Tabs/AISummaryTab";
import MindMapTab from "../Tabs/MindMapTab";
import SearchBox from "../common/SearchBox";
import SearchResultsPreview from "../common/SearchResultPreview";
import SearchResultsModal from "../Modals/SearchResultsModal";
import "../../assets/css/LeftPanel.css";
import { useAppDispatch, useAppSelector } from "../../redux/hooks";
import { setActiveTab, setShowSearchResults, setActiveStream, type SearchResult } from "../../redux/slices/uiSlice";
import { useTranslation } from 'react-i18next';
import VideoStream from "./VideoStream";
import { useContentSegmentation } from "../../redux/useContentSegmentation";
import { useSearchContent } from "../../redux/useSearchContent";

const LeftPanel = () => {
  const dispatch = useAppDispatch();
  const activeTab = useAppSelector((s) => s.ui.activeTab);
  const summaryEnabled = useAppSelector((s) => s.ui.summaryEnabled);
  const summaryLoading = useAppSelector((s) => s.ui.summaryLoading);
  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const mindmapLoading = useAppSelector((s) => s.ui.mindmapLoading);
  const searchQuery = useAppSelector((s) => s.ui.searchQuery);
  const contentSegmentationStatus = useAppSelector((s) => s.ui.contentSegmentationStatus);
  const searchLoading = useAppSelector((s) => s.ui.searchLoading);
  const searchResults = useAppSelector((s) => s.ui.searchResults);
  const showSearchResults = useAppSelector((s) => s.ui.showSearchResults);
  const uploadedVideoFiles = useAppSelector((s) => s.ui.uploadedVideoFiles);
  
  const { t } = useTranslation();
  const { shouldShowSearchBox } = useContentSegmentation();
  const { performSearch, searchError } = useSearchContent();

  const [isFullScreen, setIsFullScreen] = useState(false);

  const handleToggleFullScreen = () => {
    setIsFullScreen(!isFullScreen);
  };

  const handleSearch = (query: string) => {
    performSearch(query);
  };

  useEffect(() => {
    if (!searchResults.length) return;

    searchResults.forEach(r => {
      window.dispatchEvent(
        new CustomEvent("highlightTimeline", {
          detail: {
            startTime: r.start_time,
            endTime: r.end_time,
            topic: r.topic
          }
        })
      );
    });
  }, [searchResults]);


  const getSearchPlaceholder = () => {
    if (contentSegmentationStatus === 'loading') {
      return t('search.preparingContent', 'Content Generating...');
    }
    if (contentSegmentationStatus === 'error') {
      return t('search.contentError', 'Content preparation failed');
    }
    return t('search.placeholder', 'Search for topics...');
  };

  const showResultsPreview = searchQuery && searchResults.length >= 0 && !searchLoading;

  return (
    <div className={`left-panel-container ${isFullScreen ? "fullscreen" : ""}`}>
      <VideoStream isFullScreen={isFullScreen} onToggleFullScreen={handleToggleFullScreen} />
    
              <div className="search-container">
                <div
          className="search-wrapper"
          title={
            contentSegmentationStatus !== "complete"
              ? "Enabled only after content segmentation"
              : ""
          }
        >
        <SearchBox
          onSearch={handleSearch}
          placeholder={getSearchPlaceholder()}
          className={contentSegmentationStatus !== "complete" ? "search-disabled" : ""}
        />

        {contentSegmentationStatus === "loading" && (
          <div className="search-status loading">
            <span className="spinner"></span>
            {t('search.preparingContent', 'Content Generating...')}
          </div>
        )}

        {contentSegmentationStatus === "error" && (
          <div className="search-status error">
            {t('search.contentError', 'Content preparation failed. Search unavailable.')}
          </div>
        )}

        {searchLoading && (
          <div className="search-status loading">
            <span className="spinner"></span>
            {t('search.searching', 'Searching...')}
          </div>
        )}

        {searchError && (
          <div className="search-status error">
            {searchError}
          </div>
        )}

        {showResultsPreview && (
          <SearchResultsPreview
            results={searchResults}
            query={searchQuery}
          />
        )}
      </div>

      
      
      <div className="tabs">
        <button
          className={activeTab === "transcripts" ? "active" : ""}
          onClick={() => dispatch(setActiveTab("transcripts"))}
        >
          {t('tabs.transcripts')}
        </button>
        <button
          className={activeTab === "summary" ? "active" : ""}
          onClick={() => dispatch(setActiveTab("summary"))}
          disabled={!summaryEnabled}
          title={summaryEnabled ? t('tabs.summary') : t('tabs.summary') + " available after transcription"}
        >
          <span>{t('tabs.summary')}</span>
          {summaryEnabled && summaryLoading && <span className="tab-spinner" aria-label="loading" />}
        </button>
        <button
          className={activeTab === "mindmap" ? "active" : ""}
          onClick={() => dispatch(setActiveTab("mindmap"))}
          disabled={!mindmapEnabled}
          title={mindmapEnabled ? t('tabs.mindmap') : t('tabs.mindmap') + " available after summary"}
        >
          <span>{t('tabs.mindmap')}</span>
          {mindmapEnabled && mindmapLoading && <span className="tab-spinner" aria-label="loading" />}
        </button>
      </div>
      <div className="tab-content">
        {activeTab === "transcripts" && <TranscriptsTab />}
        {activeTab === "summary" && <AISummaryTab />}
        {activeTab === "mindmap" && <MindMapTab />}
      </div>

      {showSearchResults && (
        <SearchResultsModal
          isOpen={showSearchResults}
          onClose={() => dispatch(setShowSearchResults(false))}
          results={searchResults}
          query={searchQuery}
        />
      )}</div>
    </div>
  );
};

export default LeftPanel;