import { configureStore } from '@reduxjs/toolkit';
import { useDispatch, useSelector, type TypedUseSelectorHook } from 'react-redux';
import statusReducer from './slices/statusSlice';
import metricsReducer from './slices/metricsSlice';
import frameReducer from './slices/frameSlice';
import controlReducer from './slices/controlSlice';

export const store = configureStore({
  reducer: {
    status: statusReducer,
    metrics: metricsReducer,
    frame: frameReducer,
    control: controlReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

export const useAppDispatch: () => AppDispatch = useDispatch;
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector;
