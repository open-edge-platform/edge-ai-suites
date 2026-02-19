import React, { useState } from 'react';
import Modal from './Modal';
import '../../assets/css/SearchResultsModal.css';
import { useTranslation } from 'react-i18next';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import type { SearchResult } from '../../redux/useSearchContent';
interface SearchResultsModalProps {
  isOpen: boolean;
  onClose: () => void;
  results: SearchResult[];
  query: string;
}

const SearchResultsModal: React.FC<SearchResultsModalProps> = ({
  isOpen,
  onClose,
  results,
  query
}) => {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const uploadedVideoFiles = useAppSelector((s) => s.ui.uploadedVideoFiles);
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);

  const hasBackCamera = Boolean(uploadedVideoFiles.back);

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const handleResultClick = (result: SearchResult) => {
    setSelectedResult(result);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <div className="search-results-modal modal-dialog modal modal-dialog-centered modal-lg">
        <div className="modal-header">
          <h2>{t('search.resultsTitle', 'Search Results')}</h2>

          <div className="search-query">
            <span className="query-label">{t('search.query', 'Query')}:</span>
            <span className="query-text">"{query}"</span>
          </div>

          <div className="results-count">
            {results.length} {t('search.resultsFound', 'results found')}
          </div>
        </div>

        <div className="modal-body">
          {results.length === 0 ? (
            <div className="no-results">{t('search.noResults', 'No results found.')}</div>
          ) : (
            <div className="results-list">
              {results.map((result, index) => (
                <div
                  key={index}
                  className={`result-card ${hasBackCamera ? 'clickable' : ''} ${selectedResult === result ? 'selected' : ''}`}
                  onClick={() => handleResultClick(result)}
                >
                  <div className="result-header">
                    <div className="result-topic">
                      <h3>{result.topic}</h3>
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
          )}
        </div>
      </div>
    </Modal>
  );
};

export default SearchResultsModal;
