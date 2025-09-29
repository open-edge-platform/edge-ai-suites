// import { createSlice } from '@reduxjs/toolkit';
// import type { PayloadAction } from '@reduxjs/toolkit';

// interface FileState {
//   uploadedAudioPath: string | null;
//   sessionId: string | null;
// }

// const initialState: FileState = { uploadedAudioPath: null, sessionId: null };

// const fileSlice = createSlice({
//   name: 'file',
//   initialState,
//   reducers: {
//     setUploadedAudioPath(state, action: PayloadAction<string>) {
//       state.uploadedAudioPath = action.payload;
//     },
//     setSessionId(state, action: PayloadAction<string | null>) {
//       state.sessionId = action.payload;
//     },
//     resetFile: () => initialState,
//   },
// });

// export const { setUploadedAudioPath, setSessionId, resetFile } = fileSlice.actions;
// export default fileSlice.reducer;