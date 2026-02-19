import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../redux/hooks';
import { 
  startContentSegmentation, 
  contentSegmentationSuccess, 
  contentSegmentationFailed 
} from '../redux/slices/uiSlice';
import { generateContentSegmentation } from '../services/api';

export const useContentSegmentation = () => {
  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const contentSegmentationStatus = useAppSelector((s) => s.ui.contentSegmentationStatus);
  const audioStatus = useAppSelector((s) => s.ui.audioStatus);
  const uploadedAudioPath = useAppSelector((s) => s.ui.uploadedAudioPath);
  const uploadedVideoFiles = useAppSelector((s) => s.ui.uploadedVideoFiles);
  const videoStatus = useAppSelector((s) => s.ui.videoStatus);

  // Check if user uploaded audio files (not microphone recording)
  const hasUploadedAudio = Boolean(
    uploadedAudioPath && 
    uploadedAudioPath !== "MICROPHONE" && 
    uploadedAudioPath.trim() !== ""
  );

  // Check if user uploaded video files
  const hasUploadedVideo = Boolean(
    uploadedVideoFiles.front ||
    uploadedVideoFiles.back ||
    uploadedVideoFiles.board
  );

  // Check if mindmap processing is complete
  const isMindmapComplete = audioStatus === "complete" || audioStatus === "error";

  // Check if we're in playback mode
  const isPlaybackMode = Boolean(
    videoStatus === "completed" &&
    (uploadedVideoFiles.front ||
     uploadedVideoFiles.back ||
     uploadedVideoFiles.board)
  );

  // Determine when to trigger content segmentation
  const shouldTriggerContentSegmentation = () => {
    // Only trigger if we have audio and mindmap is complete
    if (!hasUploadedAudio || !isMindmapComplete) return false;
    
    // For audio-only: trigger when mindmap is complete
    if (hasUploadedAudio && !hasUploadedVideo && isMindmapComplete) {
      return true;
    }

    // For audio+video: trigger when mindmap is complete AND in playback mode
    if (hasUploadedAudio && hasUploadedVideo && isMindmapComplete && isPlaybackMode) {
      return true;
    }

    return false;
  };

  useEffect(() => {
    const shouldTrigger = shouldTriggerContentSegmentation();
    
    if (shouldTrigger && 
        sessionId && 
        contentSegmentationStatus === 'idle') {
      
      console.log('🔄 Starting content segmentation for session:', sessionId);
      dispatch(startContentSegmentation());
      
      generateContentSegmentation(sessionId)
        .then(() => {
          console.log('✅ Content segmentation completed');
          dispatch(contentSegmentationSuccess());
        })
        .catch((error) => {
          console.error('❌ Content segmentation failed:', error);
          dispatch(contentSegmentationFailed());
        });
    }
  }, [
    shouldTriggerContentSegmentation(),
    sessionId,
    contentSegmentationStatus,
    dispatch
  ]);

  return {
    contentSegmentationStatus,
    shouldShowSearchBox: shouldTriggerContentSegmentation() && contentSegmentationStatus === 'complete'
  };
};