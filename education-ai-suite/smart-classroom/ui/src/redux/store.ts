import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import transcriptReducer from './slices/transcriptSlice';
import summaryReducer from './slices/summarySlice';
import classStatisticsReducer from './slices/fetchClassStatistics';
import mindmapReducer from './slices/mindmapSlice';
import resourceReducer from './slices/resourceSlice';
import mediaValidationReducer from './slices/mediaValidationSlice';

export const store = configureStore({
  reducer: {
    ui: uiReducer,
    transcript: transcriptReducer,
    summary: summaryReducer,
    classStatistics: classStatisticsReducer,
    mindmap: mindmapReducer,
    resource: resourceReducer,
    mediaValidation: mediaValidationReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        // Ignore File objects in uploadedVideoFiles - we need them for duration extraction
        ignoredPaths: ['ui.uploadedVideoFiles'],
      },
    }),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;