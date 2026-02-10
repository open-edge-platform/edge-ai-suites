import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface StandReid {
  student_id: number;
  count: number;
}

interface ClassStatistics {
  student_count: number;
  stand_count: number;
  raise_up_count: number;
  stand_reid: StandReid[];
}

interface ClassStatisticsState {
  statistics: ClassStatistics;
  lastUpdated: number | null;
  isStreaming: boolean;
  error: string | null;
}

const initialState: ClassStatisticsState = {
  statistics: {
    student_count: 0,
    stand_count: 0,
    raise_up_count: 0,
    stand_reid: [],
  },
  lastUpdated: null,
  isStreaming: false,
  error: null,
};

const classStatisticsSlice = createSlice({
  name: 'classStatistics',
  initialState,
  reducers: {
    setClassStatistics: (state, action: PayloadAction<ClassStatistics>) => {
      state.statistics = action.payload;
      state.lastUpdated = Date.now();
      state.error = null;
    },
    setStreamingStatus: (state, action: PayloadAction<boolean>) => {
      state.isStreaming = action.payload;
    },
    setError: (state, action: PayloadAction<string>) => {
      state.error = action.payload;
      state.isStreaming = false;
    },
    clearError: (state) => {
      state.error = null;
    },
    clearClassStatistics: (state) => {
      state.statistics = initialState.statistics;
      state.lastUpdated = null;
      state.isStreaming = false;
      state.error = null;
    },
  },
});

export const { 
  setClassStatistics, 
  setStreamingStatus, 
  setError, 
  clearError, 
  clearClassStatistics 
} = classStatisticsSlice.actions;

export default classStatisticsSlice.reducer;