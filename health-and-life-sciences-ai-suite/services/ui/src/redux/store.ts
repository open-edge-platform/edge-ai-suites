// src/redux/store.ts
import { configureStore } from '@reduxjs/toolkit';
import appReducer from './slices/appSlice';
import servicesReducer from './slices/servicesSlice';
import eventsReducer from './slices/eventsSlice';
import { sseMiddleware } from './middleware/sseMiddleware';

export const store = configureStore({
  reducer: {
    app: appReducer,
    services: servicesReducer,
    events: eventsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: ['sse/connect', 'sse/disconnect'],
      },
    }).concat(sseMiddleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;