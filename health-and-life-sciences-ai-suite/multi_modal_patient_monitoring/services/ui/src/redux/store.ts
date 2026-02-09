// src/redux/store.ts
import { configureStore } from '@reduxjs/toolkit';
import appReducer from './slices/appSlice';
import servicesReducer from './slices/servicesSlice';
import eventsReducer from './slices/eventsSlice';
import { sseMiddleware } from './middleware/sseMiddleware';
import metricsReducer from './slices/metricsSlics';

export const store = configureStore({
  reducer: {
    app: appReducer,
    services: servicesReducer,
    events: eventsReducer,
    metrics: metricsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(sseMiddleware), // ← Should be here
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;