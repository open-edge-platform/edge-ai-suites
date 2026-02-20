import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import "../../assets/css/SearchBox.css";

interface SearchBoxProps {
  onSearch: (query: string) => void;
  placeholder?: string;
  className?: string;
}

const SearchBox: React.FC<SearchBoxProps> = ({ 
  onSearch, 
  placeholder,
  className = "" 
}) => {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchQuery(value);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      onSearch(searchQuery.trim());
    }
  };

  const handleSearchClick = () => {
    if (searchQuery.trim()) {
      onSearch(searchQuery.trim());
    }
  };

  const handleClear = () => {
    setSearchQuery("");
    onSearch(""); 
  };

  return (
    <div className={`search-box-container ${className}`}>
      <form onSubmit={handleSubmit} className="search-form">
        <div className="search-input-wrapper">
          <input
            type="text"
            value={searchQuery}
            onChange={handleInputChange}
            placeholder={placeholder || t('search.placeholder', 'Search for topics...')}
            className="search-input"
          />
          
          {searchQuery && (
            <button
              type="button"
              onClick={handleClear}
              className="search-clear-btn"
              aria-label={t('search.clear', 'Clear search')}
            >
              ×
            </button>
          )}
          
          <button
            type="button"
            onClick={handleSearchClick}
            className="search-submit-btn"
            aria-label={t('search.submit', 'Search')}
            disabled={!searchQuery.trim()}
          >
            <svg 
              width="16" 
              height="16" 
              viewBox="0 0 24 24" 
              fill="none" 
              stroke="currentColor" 
              strokeWidth="2"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
          </button>
        </div>
      </form>
    </div>
  );
};

export default SearchBox;