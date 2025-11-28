import React, { useState, useEffect } from 'react';
import NotificationsDisplay from '../Display/NotificationsDisplay';
import ProjectNameDisplay from '../Display/ProjectNameDisplay';
import '../../assets/css/HeaderBar.css';
import recordON from '../../assets/images/recording-on.svg';
import recordOFF from '../../assets/images/recording-off.svg';
import sideRecordIcon from '../../assets/images/sideRecord.svg';
import { constants } from '../../constants';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { 
  resetFlow, 
  startProcessing, 
  setUploadedAudioPath, 
  processingFailed,
  setVideoAnalyticsActive,
  setVideoAnalyticsLoading,
  loadCameraSettingsFromStorage,
  setFrontCameraStream,
  setBackCameraStream,
  setBoardCameraStream,
  setActiveStream
} from '../../redux/slices/uiSlice';
import { resetTranscript } from '../../redux/slices/transcriptSlice';
import { resetSummary } from '../../redux/slices/summarySlice';
import { clearMindmap } from '../../redux/slices/mindmapSlice';
import { useTranslation } from 'react-i18next';
import { 
  uploadAudio, 
  stopMicrophone, 
  getAudioDevices,
  startVideoAnalytics,
  stopVideoAnalytics 
} from '../../services/api';
import Toast from '../common/Toast';
import UploadFilesModal from '../Modals/UploadFilesModal';

// Safe error extraction helper
type ApiError = { response?: { data?: { message?: string } } };
const getErrorMessage = (err: unknown, fallback: string) => {
  if (err && typeof err === 'object') {
    const resp = (err as ApiError).response;
    const msg = resp?.data?.message;
    if (typeof msg === 'string' && msg.trim() !== '') return msg;
  }
  return fallback;
};

interface HeaderBarProps {
  projectName: string;
  setProjectName: (name: string) => void;
}

const HeaderBar: React.FC<HeaderBarProps> = ({ projectName }) => {
  const [showToast, setShowToast] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [notification, setNotification] = useState(constants.START_NOTIFICATION);
  const [hasAudioDevices, setHasAudioDevices] = useState(true);
  const { t } = useTranslation();
  const [timer, setTimer] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [videoAnalyticsEnabled, setVideoAnalyticsEnabled] = useState(true); // Allow disabling video analytics

  const dispatch = useAppDispatch();
  const isBusy = useAppSelector((s) => s.ui.aiProcessing);
  const summaryEnabled = useAppSelector((s) => s.ui.summaryEnabled);
  const summaryLoading = useAppSelector((s) => s.ui.summaryLoading);
  const transcriptStatus = useAppSelector((s) => s.transcript.status);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false); 

  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const mindmapLoading = useAppSelector((s) => s.ui.mindmapLoading);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const projectLocation = useAppSelector((s) => s.ui.projectLocation);
  const mindmapState = useAppSelector((s) => s.mindmap);
  
  // Camera settings from Redux
  const frontCamera = useAppSelector((s) => s.ui.frontCamera);
  const backCamera = useAppSelector((s) => s.ui.backCamera);
  const boardCamera = useAppSelector((s) => s.ui.boardCamera);
  const videoAnalyticsActive = useAppSelector((s) => s.ui.videoAnalyticsActive);

  // Load camera settings from localStorage on component mount
  useEffect(() => {
    dispatch(loadCameraSettingsFromStorage());
  }, [dispatch]);

  const handleOpenUploadModal = () => {
    setIsUploadModalOpen(true);
  };

  const handleCloseUploadModal = () => {
    setIsUploadModalOpen(false);
  };

  const clearForNewOp = () => setErrorMsg(null);
  
  const handleCopy = async () => {
    try {
      const location = `${projectLocation}/${projectName}/${sessionId}`;
      await navigator.clipboard.writeText(location);
      setShowToast(true);
    } catch {
      setErrorMsg('Failed to copy path');
    }
  };

  const handleClose = () => setShowToast(false);

  useEffect(() => {
    const checkAudioDevices = async () => {
      try {
        const devices = await getAudioDevices();
        setHasAudioDevices(devices.length > 0);
        console.log('Audio devices available:', devices.length > 0, devices);
      } catch (error) {
        console.error('Failed to check audio devices:', error);
        setHasAudioDevices(false);
      }
    };

    checkAudioDevices();
  }, []);

  useEffect(() => {
    let interval: number | undefined;
    if (isRecording) {
      interval = window.setInterval(() => setTimer((t) => t + 1), 1000);
    } else {
      if (interval) clearInterval(interval);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  useEffect(() => {
    if (mindmapState.error) {
      setNotification(t('notifications.mindmapError'));
    }
    else if (mindmapLoading || mindmapState.isLoading) {
      setNotification(t('notifications.generatingMindmap'));
    }
    else if (mindmapEnabled && !mindmapLoading && mindmapState.finalText) {
      setNotification(t('notifications.mindmapReady'));
    }
    else if (summaryEnabled && summaryLoading) {
      setNotification(t('notifications.generatingSummary'));
    } 
    else if (summaryEnabled && isBusy && !summaryLoading) {
      setNotification(t('notifications.streamingSummary'));
    } 
    else if (!isBusy && summaryEnabled && !mindmapEnabled) {
      setNotification(t('notifications.summaryReady'));
    }
    else if (isBusy && transcriptStatus === 'streaming') {
      setNotification(t('notifications.loadingTranscript'));
    } 
    else if (isBusy && !summaryEnabled) {
      setNotification(t('notifications.analyzingAudio'));
    } 
    else {
      setNotification(t('notifications.start'));
    }
  }, [
    isBusy,
    summaryEnabled,
    summaryLoading,
    transcriptStatus,
    mindmapEnabled,
    mindmapLoading,
    mindmapState.isLoading,
    mindmapState.finalText,
    mindmapState.error,
    t
  ]);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      setErrorMsg(detail || 'An error occurred');
    };
    window.addEventListener('global-error', handler as EventListener);
    return () => window.removeEventListener('global-error', handler as EventListener);
  }, []);

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  // Updated logic: Only disable START recording when conditions prevent it
  // Allow STOP recording when recording is active
  const isRecordingDisabled =
    (!isRecording && ( // Only disable START recording when these conditions are true
      isBusy ||
      transcriptStatus === 'streaming' ||     
      summaryLoading ||                         
      (mindmapEnabled && (
        mindmapLoading ||
        mindmapState.isLoading ||
        !mindmapState.finalText                
      )) ||
      !hasAudioDevices
    ));

  const isUploadDisabled =
    isRecording ||
    transcriptStatus === 'streaming' ||      
    isBusy ||                                
    summaryLoading ||                         
    (mindmapEnabled && (
      mindmapLoading ||
      mindmapState.isLoading ||
      !mindmapState.finalText                
    ));

  const tryStartVideoAnalytics = async (currentSessionId: string) => {
    if (!videoAnalyticsEnabled) {
      console.log('🎥 Video analytics disabled, skipping');
      return;
    }

    try {
      // Get current camera settings
      const currentFrontCamera = frontCamera || localStorage.getItem('frontCamera') || '';
      const currentBackCamera = backCamera || localStorage.getItem('backCamera') || '';
      const currentBoardCamera = boardCamera || localStorage.getItem('boardCamera') || '';

      console.log('🎥 Current camera settings:', {
        front: currentFrontCamera,
        back: currentBackCamera,
        board: currentBoardCamera
      });

      // Only attempt if cameras are configured
      if (!currentFrontCamera.trim() && !currentBackCamera.trim() && !currentBoardCamera.trim()) {
        console.log('🎥 No cameras configured, skipping video analytics');
        return;
      }

      // Prepare requests for configured cameras only
      const videoRequests = [];
      if (currentFrontCamera.trim()) {
        videoRequests.push({ pipeline_name: 'front', source: currentFrontCamera.trim() });
      }
      if (currentBackCamera.trim()) {
        videoRequests.push({ pipeline_name: 'back', source: currentBackCamera.trim() });
      }
      if (currentBoardCamera.trim()) {
        videoRequests.push({ pipeline_name: 'content', source: currentBoardCamera.trim() });
      }

      if (videoRequests.length === 0) {
        console.log('🎥 No valid camera configurations found');
        return;
      }

      console.log('🎥 Attempting to start video analytics with requests:', videoRequests);
      dispatch(setVideoAnalyticsLoading(true));
      
      const videoResult = await startVideoAnalytics(videoRequests, currentSessionId);
      console.log('🎥 Video analytics result:', videoResult);
      
      // Process results
      if (videoResult && videoResult.results) {
        let hasSuccessfulStreams = false;
        let successfulPipelines: any[] = [];
        let failedPipelines: { name: any; error: any; }[] = [];
        
        videoResult.results.forEach((result: any) => {
          if (result.status === 'success' && result.hls_stream) {
            hasSuccessfulStreams = true;
            successfulPipelines.push(result.pipeline_name);
            console.log(`✅ ${result.pipeline_name} stream started:`, result.hls_stream);
            
            // Set stream URLs in Redux
            switch (result.pipeline_name) {
              case 'front':
                dispatch(setFrontCameraStream(result.hls_stream));
                break;
              case 'back':
                dispatch(setBackCameraStream(result.hls_stream));
                break;
              case 'content':
                dispatch(setBoardCameraStream(result.hls_stream));
                break;
            }
          } else {
            failedPipelines.push({
              name: result.pipeline_name,
              error: result.error
            });
            console.warn(`⚠️ ${result.pipeline_name} failed:`, result.error);
          }
        });
        
        if (hasSuccessfulStreams) {
          dispatch(setVideoAnalyticsActive(true));
          dispatch(setActiveStream('all'));
          console.log(`🎥 Video analytics partially successful. Working: ${successfulPipelines.join(', ')}`);
          
          if (failedPipelines.length > 0) {
            const failedNames = failedPipelines.map(p => p.name).join(', ');
            console.warn(`⚠️ Some cameras failed: ${failedNames}`);
            // Don't show error for partial failures
          }
        } else {
          console.warn('🎥 All video streams failed to start');
          console.warn('🎥 This is likely due to backend video analytics service configuration');
          console.warn('🎥 Audio recording will continue without video analytics');
          
          // Don't show error - just continue without video analytics
          dispatch(setVideoAnalyticsActive(false));
        }
      }
      
    } catch (videoError) {
      console.warn('🎥 Video analytics failed:', videoError);
      console.warn('🎥 Continuing with audio-only recording');
      dispatch(setVideoAnalyticsActive(false));
      
      // Don't show error to user - video analytics is optional
    } finally {
      dispatch(setVideoAnalyticsLoading(false));
    }
  };

  const handleRecordingToggle = async () => {
    if (isRecordingDisabled) return;

    const next = !isRecording;
    clearForNewOp();

    if (next) {
      // 🎙️ Start Recording
      setTimer(0);
      setNotification(t('notifications.recording'));
      dispatch(resetFlow());
      dispatch(resetTranscript());
      dispatch(resetSummary());
      dispatch(startProcessing());
      dispatch(clearMindmap());

      try {
        dispatch(setUploadedAudioPath('MICROPHONE'));
        setIsRecording(true);
        
        console.log('🎙️ Microphone recording started - transcription will begin automatically');
        
        // Wait for sessionId and optionally start video analytics
        const checkSessionAndStartVideo = async () => {
          let attempts = 0;
          const maxAttempts = 10;
          
          const checkSession = async () => {
            const currentSessionId = sessionId;
            if (currentSessionId && attempts < maxAttempts) {
              // Try to start video analytics (non-blocking)
              await tryStartVideoAnalytics(currentSessionId);
            } else if (attempts < maxAttempts) {
              attempts++;
              console.log(`⏳ Waiting for session ID... attempt ${attempts}/${maxAttempts}`);
              setTimeout(checkSession, 1000);
            } else {
              console.warn('Session ID not available after maximum attempts');
              dispatch(setVideoAnalyticsLoading(false));
            }
          };
          
          checkSession();
        };

        checkSessionAndStartVideo();
        
      } catch (error) {
        console.error('Failed to start microphone:', error);
        setErrorMsg('Failed to start microphone recording');
        dispatch(processingFailed());
        setIsRecording(false);
      }
    } else {
      // 🛑 Stop Recording
      setIsRecording(false);
      
      try {
        if (sessionId) {
          // Stop microphone
          const result = await stopMicrophone(sessionId);
          console.log('🛑 Microphone stopped:', result);

          // Stop video analytics if active (gracefully)
          if (videoAnalyticsActive) {
            try {
              const videoRequests = [
                { pipeline_name: 'front' },
                { pipeline_name: 'back' },
                { pipeline_name: 'content' },
              ];

              console.log('🛑 Stopping video analytics');
              const videoResult = await stopVideoAnalytics(videoRequests, sessionId);
              console.log('🛑 Video analytics stopped:', videoResult);
            } catch (videoError) {
              console.warn('Failed to stop video analytics (non-critical):', videoError);
            }
          }

          // Always clear video analytics state
          dispatch(setFrontCameraStream(''));
          dispatch(setBackCameraStream(''));
          dispatch(setBoardCameraStream(''));
          dispatch(setActiveStream(null));
          dispatch(setVideoAnalyticsActive(false));
        } else {
          console.warn('No session ID available to stop recording');
        }
      } catch (error) {
        console.error('Failed to stop recording:', error);
        setErrorMsg('Failed to stop recording');
      }
    }
  };

  return (
    <div className="header-bar">
      <div className="navbar-left">
        <img
          src={isRecording ? recordON : recordOFF}
          alt="Record"
          className="record-icon"
          onClick={handleRecordingToggle}
          style={{
            opacity: isRecordingDisabled ? 0.5 : 1,
            cursor: isRecordingDisabled ? 'not-allowed' : 'pointer'
          }}
        />
        <img src={sideRecordIcon} alt="Side Record" className="side-record-icon" />
        <span className="timer">{formatTime(timer)}</span>

        <button
          className="text-button"
          onClick={handleRecordingToggle}
          disabled={isRecordingDisabled}
          style={{
            cursor: isRecordingDisabled ? 'not-allowed' : 'pointer',
            opacity: isRecordingDisabled ? 0.6 : 1
          }}
        >
          {isRecording ? t('header.stopRecording') : t('header.startRecording')}
        </button>

        <button
          className="upload-button"
          disabled={isUploadDisabled}   
          onClick={!isUploadDisabled ? handleOpenUploadModal : undefined} 
          style={{
            opacity: isUploadDisabled ? 0.6 : 1,                           
            cursor: isUploadDisabled ? 'not-allowed' : 'pointer'            
          }}
        >
          {t('header.uploadFile')}
        </button>

      </div>

      <div className="navbar-center">
        <NotificationsDisplay notification={notification} error={errorMsg} />
      </div>

      <div className="navbar-right">
        <ProjectNameDisplay projectName={projectName} />
      </div>

      {showToast && (
        <Toast
          message={`Copied path: ${projectLocation}/${projectName}/${sessionId}`}
          onClose={handleClose}
          onCopy={handleCopy}
        />
      )}
      {isUploadModalOpen && (
        <UploadFilesModal isOpen={isUploadModalOpen} onClose={handleCloseUploadModal} />
      )}
    </div>
  );
};

export default HeaderBar;