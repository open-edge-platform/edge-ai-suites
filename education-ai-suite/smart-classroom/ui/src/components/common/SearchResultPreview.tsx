import React, { useState } from 'react';
import '../../assets/css/SearchResultsPreview.css';
import { useTranslation } from 'react-i18next';
import { useAppSelector } from '../../redux/hooks';
import { type SearchResult } from '../../redux/useSearchContent';

interface SearchResultsPreviewProps {
  results: SearchResult[];
  query: string;
}

const SearchResultsPreview: React.FC<SearchResultsPreviewProps> = ({
  results,
  query
}) => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const uploadedVideoFiles = useAppSelector((s) => s.ui.uploadedVideoFiles);
  
  const hasBackCamera = Boolean(uploadedVideoFiles.back);

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const handleToggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  const handleResultClick = (result: SearchResult) => {
    console.log('Selected result:', result);
  };

  if (results.length === 0) {
    return (
      <div className="search-results-preview">
        <div className="preview-header">
          <span className="results-count">
            {t('search.noResults', 'No results found')} for "{query}"
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="search-results-preview">
      <div className="preview-header" onClick={handleToggleExpand}>
        <span className="results-count">
          {results.length} {t('search.resultsFound', 'results found')} for "{query}"
        </span>

        <button 
          className={`dropdown-btn ${isExpanded ? 'expanded' : ''}`}
          title={isExpanded ? t('search.collapseResults', 'Collapse results') : t('search.expandResults', 'Show results')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points={isExpanded ? "18,15 12,9 6,15" : "6,9 12,15 18,9"}></polyline>
          </svg>
        </button>
      </div>

      {isExpanded && (
        <div className="results-dropdown">
          <div className="results-list">
            {results.map((result, index) => (
              <div
                key={index}
                className={`result-card ${hasBackCamera ? 'clickable' : ''}`}
                onClick={() => handleResultClick(result)}
              >
                <div className="result-header">
                  <div className="result-topic">
                    <h4>{result.topic}</h4>
                    <span className="relevance-score">
                      {(result.score * 100).toFixed(0)}%
                    </span>
                  </div>

                  <div className="result-timestamp">
                    <span className="time-range">
                      {formatTime(result.start_time)} – {formatTime(result.end_time)}
                    </span>
                    <span className="duration">
                      {Math.round(result.end_time - result.start_time)}s
                    </span>
                  </div>
                </div>

                <div className="result-content">
                  <p className="result-text">{result.text}</p>
                </div>

                <div className="result-footer">
                  <span className="score-detail">
                    {t('search.Relevance', 'Relevance')}: {(result.score * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchResultsPreview;