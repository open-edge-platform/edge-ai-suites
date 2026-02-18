import { useAppDispatch, useAppSelector } from '../redux/hooks';
import { 
  setSearchQuery, 
  setSearchResults, 
  clearSearchResults,
  setSearchLoading,
  setSearchError,
  setActiveStream
} from '../redux/slices/uiSlice';
import { searchContent } from '../services/api';

export interface SearchResult {
  score: number;
  session_id: string;
  topic: string;
  start_time: number;
  end_time: number;
  text: string;
}

export const useSearchContent = () => {
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const searchLoading = useAppSelector((s) => s.ui.searchLoading);
  const searchError = useAppSelector((s) => s.ui.searchError);
  const uploadedVideoFiles = useAppSelector((s) => s.ui.uploadedVideoFiles);

  const performSearch = async (query: string) => {
    if (!sessionId) {
      console.error('No session ID available for search');
      return;
    }

    if (!query.trim()) {
      dispatch(setSearchQuery(''));
      dispatch(clearSearchResults());
      dispatch(setSearchError(null));
      return;
    }

    dispatch(setSearchQuery(query));
    dispatch(setSearchLoading(true));
    dispatch(setSearchError(null));

    try {
      console.log('🔍 Searching content:', query);
      const results = await searchContent(sessionId, query, 10);
      
      console.log('✅ Search results:', results);
      
      dispatch(setSearchResults(results.results || []));
  
      if (results.results && results.results.length > 0 && uploadedVideoFiles.back) {
        dispatch(setActiveStream('back'));
        console.log('🎥 Switched to back camera for search results');
      }

    } catch (error) {
      console.error('❌ Search failed:', error);
      dispatch(setSearchError(error instanceof Error ? error.message : 'Search failed'));
      dispatch(clearSearchResults());
    } finally {
      dispatch(setSearchLoading(false));
    }
  };

  return {
    performSearch,
    searchLoading,
    searchError
  };
};