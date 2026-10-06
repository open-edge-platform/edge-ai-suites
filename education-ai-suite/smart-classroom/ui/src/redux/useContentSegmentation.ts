import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../redux/hooks';
import { setVideoMetadataProcessed } from '../redux/slices/mediaValidationSlice';
import { markVideoUsage, uploadVideoMetadata } from '../services/api';

/**
 * Uploads the selected video's duration so the backend can sanity-check it
 * against the audio before segmenting.
 *
 * This used to also decide *when* segmentation ran, off a combination of Redux
 * flags. It no longer does: useStageDrivenChain starts segmentation from the
 * backend's own stage table instead. The flags could not see a microphone
 * session as having audio at all, and lost the video the moment its File
 * objects were cleared, either of which silently stalled the session forever.
 *
 * Duration extraction stays on this side because only the browser has the File;
 * the backend gets a number, not a path.
 */
export const useContentSegmentation = () => {
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const uploadedVideoFiles = useAppSelector((s) => s.ui.uploadedVideoFiles);
  const videoMetadataProcessed = useAppSelector((s) => s.mediaValidation.videoMetadataProcessed);

  // Check if user uploaded video files
  const hasUploadedVideo = Boolean(
    uploadedVideoFiles.front ||
    uploadedVideoFiles.back ||
    uploadedVideoFiles.board
  );

  // Extract video duration when video files are uploaded (regardless of videoStatus)
  useEffect(() => {
    if (!hasUploadedVideo || !sessionId || videoMetadataProcessed) return;

    console.log('📹 Extracting duration for session:', sessionId);

    markVideoUsage(sessionId)
      .then(() => {
        // Priority-based video selection: Back > Board > Front
        // Only validate duration for the highest priority video
        let selectedVideo: File | null = null;
        let selectedVideoType = '';

        if (uploadedVideoFiles.back) {
          selectedVideo = uploadedVideoFiles.back;
          selectedVideoType = 'back';
        } else if (uploadedVideoFiles.board) {
          selectedVideo = uploadedVideoFiles.board;
          selectedVideoType = 'board';
        } else if (uploadedVideoFiles.front) {
          selectedVideo = uploadedVideoFiles.front;
          selectedVideoType = 'front';
        }

        if (!selectedVideo) {
          console.error('❌ No video file selected for duration extraction');
          dispatch(setVideoMetadataProcessed(true));
          return;
        }

        return uploadVideoMetadata(sessionId, selectedVideo)
          .then(() => {
            console.log(`✅ Video duration stored for ${selectedVideoType}`);
          })
          .catch((error) => {
            console.error(`❌ Could not extract video duration for ${selectedVideoType}:`, error);
          });
      })
      .catch((error) => {
        console.error('❌ Failed to mark video usage:', error);
      })
      // Marked processed however it went, so a failure cannot make this retry on
      // every render. Without the duration the backend simply skips the
      // audio/video length check (MediaValidationService treats a missing
      // duration as "single media type") — segmentation still runs.
      .finally(() => {
        dispatch(setVideoMetadataProcessed(true));
      });
  }, [hasUploadedVideo, sessionId, videoMetadataProcessed, dispatch, uploadedVideoFiles]);
};
