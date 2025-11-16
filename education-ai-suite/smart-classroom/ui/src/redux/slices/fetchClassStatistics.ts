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
}

const initialState: ClassStatisticsState = {
  statistics: {
    student_count: 0,
    stand_count: 0,
    raise_up_count: 0,
    stand_reid: [],
  },
  lastUpdated: null,
};

const classStatisticsSlice = createSlice({
  name: 'classStatistics',
  initialState,
  reducers: {
    setClassStatistics: (state, action: PayloadAction<ClassStatistics>) => {
      state.statistics = action.payload;
      state.lastUpdated = Date.now();
    },
    clearClassStatistics: (state) => {
      state.statistics = initialState.statistics;
      state.lastUpdated = null;
    },
  },
});

export const { setClassStatistics, clearClassStatistics } = classStatisticsSlice.actions;
export default classStatisticsSlice.reducer;