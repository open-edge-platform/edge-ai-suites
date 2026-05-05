// src/redux/store.ts
import { configureStore } from '@reduxjs/toolkit';
import appReducer from './slices/appSlice';
import servicesReducer from './slices/servicesSlice';
import eventsReducer from './slices/eventsSlice';
import { sseMiddleware } from './middleware/sseMiddleware';
import nicuReducer from './slices/nicuSlice';
import metricsReducer from './slices/metricsSlice';

export const store = configureStore({
  reducer: {
    app: appReducer,
    services: servicesReducer,
    events: eventsReducer,
    metrics: metricsReducer,
    nicu: nicuReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: false,
      immutableCheck: false, // optional but recommended for large streaming data
    }).concat(sseMiddleware),
});


export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;