import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import transcriptReducer from './slices/transcriptSlice';
import summaryReducer from './slices/summarySlice';
import classStatisticsReducer from './slices/fetchClassStatistics';
import resourceReducer from './slices/resourceSlice';


export const store = configureStore({
  reducer: {
    ui: uiReducer,
    transcript: transcriptReducer,
    summary: summaryReducer,
    classStatistics: classStatisticsReducer,
    resource: resourceReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;