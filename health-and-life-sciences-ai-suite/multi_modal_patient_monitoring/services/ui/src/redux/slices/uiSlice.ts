// src/redux/slices/uiSlice.ts
import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

interface UIState {
  sessionId: string | null;
  isProcessing: boolean;
  notification: string;
}

const initialState: UIState = {
  sessionId: null,
  isProcessing: false,
  notification: '',
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    setSessionId: (state, action: PayloadAction<string | null>) => {
      state.sessionId = action.payload;
      state.isProcessing = action.payload !== null;
    },
    setNotification: (state, action: PayloadAction<string>) => {
      state.notification = action.payload;
    },
  },
});

export const { setSessionId, setNotification } = uiSlice.actions;
export default uiSlice.reducer;