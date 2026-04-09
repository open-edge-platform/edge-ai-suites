import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '../redux/hooks';
import { 
  startContentSegmentation, 
  contentSegmentationSuccess, 
  contentSegmentationFailed 
} from '../redux/slices/uiSlice';
import { setVideoMetadataProcessed, resetMediaValidation } from '../redux/slices/mediaValidationSlice';
import { generateContentSegmentation, markVideoUsage, uploadVideoMetadata } from '../services/api';
import { useTranslation } from 'react-i18next';

export const useContentSegmentation = () => {
  const dispatch = useAppDispatch();
  const { t } = useTranslation();
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const contentSegmentationStatus = useAppSelector((s) => s.ui.contentSegmentationStatus);
  const audioStatus = useAppSelector((s) => s.ui.audioStatus);
  const uploadedAudioPath = useAppSelector((s) => s.ui.uploadedAudioPath);
  const uploadedVideoFiles = useAppSelector((s) => s.ui.uploadedVideoFiles);
  const videoStatus = useAppSelector((s) => s.ui.videoStatus);
  const videoPlaybackMode = useAppSelector((s) => s.ui.videoPlaybackMode);
  const videoMetadataProcessed = useAppSelector((s) => s.mediaValidation.videoMetadataProcessed);

  console.log('🚀 useContentSegmentation hook is RUNNING');

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

  // Debug logging for conditions
  useEffect(() => {
    console.log('🔍 useContentSegmentation conditions:', {
      hasUploadedVideo,
      sessionId,
      videoMetadataProcessed,
      uploadedVideoFiles: {
        front: uploadedVideoFiles.front ? `File: ${uploadedVideoFiles.front.name}` : 'null',
        back: uploadedVideoFiles.back ? `File: ${uploadedVideoFiles.back.name}` : 'null',
        board: uploadedVideoFiles.board ? `File: ${uploadedVideoFiles.board.name}` : 'null'
      }
    });
  }, [hasUploadedVideo, sessionId, videoMetadataProcessed, uploadedVideoFiles]);

  // Extract video duration when video files are uploaded (regardless of videoStatus)
  useEffect(() => {
    console.log('🎬 Video duration extraction useEffect triggered');
    console.log('   Conditions: hasUploadedVideo=' + hasUploadedVideo + ', sessionId=' + sessionId + ', videoMetadataProcessed=' + videoMetadataProcessed);
    
    if (hasUploadedVideo && sessionId && !videoMetadataProcessed) {
      console.log('📹 ✅ All conditions met - extracting duration for session:', sessionId);
      console.log('   Available video files:', {
        front: uploadedVideoFiles.front ? uploadedVideoFiles.front.name : 'none',
        back: uploadedVideoFiles.back ? uploadedVideoFiles.back.name : 'none',
        board: uploadedVideoFiles.board ? uploadedVideoFiles.board.name : 'none'
      });
      console.log('   📊 Priority order: Back > Board > Front (only highest priority will be validated)');
      
      markVideoUsage(sessionId)
        .then(() => {
          console.log('✅ Video usage marked successfully');

          // Priority-based video selection: Back > Board > Front
          // Only validate duration for the highest priority video
          let selectedVideo: File | null = null;
          let selectedVideoType = '';
          
          if (uploadedVideoFiles.back) {
            selectedVideo = uploadedVideoFiles.back;
            selectedVideoType = 'back';
            console.log('  🎯 Selected BACK video (highest priority):', selectedVideo.name);
            if (uploadedVideoFiles.board) console.log('  ⏭️  Skipping board video (lower priority)');
            if (uploadedVideoFiles.front) console.log('  ⏭️  Skipping front video (lower priority)');
          } else if (uploadedVideoFiles.board) {
            selectedVideo = uploadedVideoFiles.board;
            selectedVideoType = 'board';
            console.log('  🎯 Selected BOARD video (medium priority):', selectedVideo.name);
            if (uploadedVideoFiles.front) console.log('  ⏭️  Skipping front video (lower priority)');
          } else if (uploadedVideoFiles.front) {
            selectedVideo = uploadedVideoFiles.front;
            selectedVideoType = 'front';
            console.log('  🎯 Selected FRONT video (lowest priority):', selectedVideo.name);
          }

          if (!selectedVideo) {
            console.error('❌ No video file selected for duration extraction');
            dispatch(setVideoMetadataProcessed(true));
            return;
          }

          console.log(`📤 Processing ${selectedVideoType} video for duration validation`);
          
          // Extract and upload metadata for the selected video only
          uploadVideoMetadata(sessionId, selectedVideo)
            .then(() => {
              console.log(`✅✅✅ Video duration extracted and stored successfully for ${selectedVideoType}`);
              dispatch(setVideoMetadataProcessed(true));
            })
            .catch((error) => {
              console.error(`❌ Could not extract video duration for ${selectedVideoType}:`, error);
              dispatch(setVideoMetadataProcessed(true));
            });
        })
        .catch((error) => {
          console.error('❌ Failed to mark video usage:', error);
        });
    } else {
      console.log('❌ Conditions NOT met for video duration extraction');
      if (!hasUploadedVideo) console.log('   ❌ No uploaded video files');
      if (!sessionId) console.log('   ❌ No session ID');
      if (videoMetadataProcessed) console.log('   ❌ Video metadata already processed');
    }
  }, [hasUploadedVideo, sessionId, videoMetadataProcessed, dispatch, uploadedVideoFiles]);

  const shouldTriggerContentSegmentation = () => {
    // Condition 1: Must have audio and mindmap complete
    if (!hasUploadedAudio || !isMindmapComplete) {
      return false;
    }

    // Condition 2: AUDIO ONLY (no video)
    if (hasUploadedAudio && !hasUploadedVideo && isMindmapComplete) {
      return true;
    }

    // Condition 3: AUDIO + VIDEO (both uploaded)
    // Requires: mindmap complete + video metadata processed + playback mode activated
    if (hasUploadedAudio && hasUploadedVideo && isMindmapComplete && videoMetadataProcessed && videoPlaybackMode) {
      console.log('✨ Trigger: Audio+Video mode + mindmap complete + playback mode activated');
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
          const errorMsg = error.message || '';
          let userFriendlyError = '';
          
          if (errorMsg.includes('duration mismatch') || errorMsg.includes('Media duration mismatch')) {
            userFriendlyError = t('search.durationMismatch', '⚠️ Audio and video durations don\'t match. Please ensure both files have similar lengths.');
          } else if (errorMsg.includes('duration')) {
            userFriendlyError = t('search.durationExtractionFailed', '⚠️ Unable to extract audio or video duration. Please check your files and try again.');
          } else {
            userFriendlyError = t('search.contentPreparationFailed', 'Content preparation failed. Please try again.');
          }
          
          dispatch(contentSegmentationFailed(userFriendlyError));
        });
    } 
  }, [
    shouldTriggerContentSegmentation(),
    sessionId,
    contentSegmentationStatus,
    dispatch,
    hasUploadedAudio,
    hasUploadedVideo,
    isMindmapComplete,
    videoMetadataProcessed,
    videoPlaybackMode
  ]);

  return {
    contentSegmentationStatus,
    shouldShowSearchBox: shouldTriggerContentSegmentation() && contentSegmentationStatus === 'complete'
  };
};