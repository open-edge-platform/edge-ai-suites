import React from 'react';
import '../../assets/css/SearchResultsPreview.css';
import { useTranslation } from 'react-i18next';
import { useAppDispatch } from '../../redux/hooks';
import { setShowSearchResults } from '../../redux/slices/uiSlice';
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
  const dispatch = useAppDispatch();

  const handleExpandClick = () => {
    dispatch(setShowSearchResults(true));
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
    <div className="search-results-preview compact">
      <div className="preview-header">
        <span className="results-count">
          {results.length} {t('search.resultsFound', 'results found')} for "{query}"
        </span>

        <button 
          className="expand-btn"
          onClick={handleExpandClick}
          title={t('search.expandResults', 'Expand all results')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="15,3 21,3 21,9"></polyline>
            <polyline points="9,21 3,21 3,15"></polyline>
            <line x1="21" y1="3" x2="14" y2="10"></line>
            <line x1="3" y1="21" x2="10" y2="14"></line>
          </svg>
          {t('search.expandAll', 'Expand All')}
        </button>
      </div>
    </div>
  );
};

export default SearchResultsPreview;
