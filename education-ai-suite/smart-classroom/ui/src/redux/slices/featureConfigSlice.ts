import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

/**
 * Feature descriptor shape from backend /features endpoint
 */
export interface FeatureDescriptor {
  id: string;
  dependency: string[];
  requires: string[];
  
  // Optional UI-specific fields
  endpoints?: Record<string, string>;
  mode?: string;
  chunking?: boolean;
  diarization?: boolean;
}

interface FeatureConfigState {
  features: FeatureDescriptor[];
  loaded: boolean;
  loading: boolean;
  error: string | null;
}

const initialState: FeatureConfigState = {
  features: [],
  loaded: false,
  loading: false,
  error: null,
};

const featureConfigSlice = createSlice({
  name: 'featureConfig',
  initialState,
  reducers: {
    startLoading(state) {
      state.loading = true;
      state.error = null;
    },
    
    setFeatures(state, action: PayloadAction<FeatureDescriptor[]>) {
      state.features = action.payload;
      state.loaded = true;
      state.loading = false;
      state.error = null;
    },
    
    setError(state, action: PayloadAction<string>) {
      state.error = action.payload;
      state.loaded = false;
      state.loading = false;
    },
    
    reset(state) {
      state.features = [];
      state.loaded = false;
      state.loading = false;
      state.error = null;
    },
  },
});

export const { startLoading, setFeatures, setError, reset } = featureConfigSlice.actions;
export default featureConfigSlice.reducer;
