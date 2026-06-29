import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export interface FrameState {
  /** epoch seconds — last successful MJPEG frame */
  lastUpdate: number;
  /** stream stalled if last update older than freshnessThresholdS */
  freshnessThresholdS: number;
  /** monotonic counter for `<img src=...?v=N>` cache-bust on demand */
  refreshTick: number;
}

const initialState: FrameState = {
  lastUpdate: 0,
  freshnessThresholdS: 1.0,
  refreshTick: 0,
};

const frameSlice = createSlice({
  name: 'frame',
  initialState,
  reducers: {
    markFrameReceived(state) {
      state.lastUpdate = Date.now() / 1000;
    },
    bumpRefresh(state) {
      state.refreshTick += 1;
    },
    setFreshnessThreshold(state, action: PayloadAction<number>) {
      state.freshnessThresholdS = action.payload;
    },
  },
});

export const { markFrameReceived, bumpRefresh, setFreshnessThreshold } = frameSlice.actions;
export default frameSlice.reducer;
