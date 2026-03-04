import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';

interface MediaValidationState {
  videoMetadataProcessed: boolean;
}

const initialState: MediaValidationState = {
  videoMetadataProcessed: false,
};

const mediaValidationSlice = createSlice({
  name: 'mediaValidation',
  initialState,
  reducers: {
    setVideoMetadataProcessed: (state, action: PayloadAction<boolean>) => {
      console.log('🔧 setVideoMetadataProcessed:', action.payload);
      state.videoMetadataProcessed = action.payload;
    },
    resetMediaValidation: (state) => {
      console.log('🔄 resetMediaValidation called - resetting videoMetadataProcessed to false');
      state.videoMetadataProcessed = false;
    },
  },
});

export const { setVideoMetadataProcessed, resetMediaValidation } = mediaValidationSlice.actions;
export default mediaValidationSlice.reducer;
