import { configureStore } from '@reduxjs/toolkit';
import uiReducer from './slices/uiSlice';
import transcriptReducer from './slices/transcriptSlice';
import summaryReducer from './slices/summarySlice';
// import fileReducer from './slices/fileSlice';
import resourceReducer from './slices/resourceSlice';


export const store = configureStore({
  reducer: {
    ui: uiReducer,
    transcript: transcriptReducer,
    summary: summaryReducer,
    // file: fileReducer,
    resource: resourceReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;