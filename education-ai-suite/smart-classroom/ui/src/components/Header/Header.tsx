import React, { useState, useEffect, useMemo } from 'react';
import NotificationsDisplay from '../Display/NotificationsDisplay';
import ProjectNameDisplay from '../Display/ProjectNameDisplay';
import '../../assets/css/HeaderBar.css';
import recordON from '../../assets/images/recording-on.svg';
import recordOFF from '../../assets/images/recording-off.svg';
import sideRecordIcon from '../../assets/images/sideRecord.svg';
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
  setActiveStream,
  startStream,
  setProcessingMode,
  setSessionId,
  setHasAudioDevices,
  setAudioDevicesLoading,
  setIsRecording,
  setJustStoppedRecording,
  setVideoAnalyticsStopping,
  setAudioStatus,
  setVideoStatus,
  startTranscription,
  setMonitoringActive,
  setUploadedVideoFiles,
  setHasUploadedVideoFiles,
  setVideoPlaybackMode,
  setRecordedVideoType,
} from '../../redux/slices/uiSlice';
import { resetTranscript } from '../../redux/slices/transcriptSlice';
import { resetSummary } from '../../redux/slices/summarySlice';
import { clearMindmap } from '../../redux/slices/mindmapSlice';
import { useTranslation } from 'react-i18next';
import { 
  stopMicrophone, 
  getAudioDevices,
  startVideoAnalytics,
  stopVideoAnalytics,
  createSession,
  startMonitoring,  
  stopMonitoring,
  startPipelineMonitoring,
  checkRecordedVideos,
} from '../../services/api';
import Toast from '../common/Toast';
import UploadFilesModal from '../Modals/UploadFilesModal';

interface HeaderBarProps {
  projectName: string;
  setProjectName: (name: string) => void;
}

const HeaderBar: React.FC<HeaderBarProps> = ({ projectName }) => {
  const [showToast, setShowToast] = useState(false);
  const [audioNotification, setAudioNotification] = useState('');
  const [videoNotification, setVideoNotification] = useState('');
  const { t } = useTranslation();
  const [timer, setTimer] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [videoAnalyticsEnabled] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false); 
  const monitoringActive = useAppSelector((s) => s.ui.monitoringActive);
  const dispatch = useAppDispatch();
  const summaryEnabled = useAppSelector((s) => s.ui.summaryEnabled);
  const summaryLoading = useAppSelector((s) => s.ui.summaryLoading);
  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const projectLocation = useAppSelector((s) => s.ui.projectLocation);
  const mindmapState = useAppSelector((s) => s.mindmap);
  const processingMode = useAppSelector((s) => s.ui.processingMode);
  const uploadedAudioPath = useAppSelector((s) => s.ui.uploadedAudioPath);
  const frontCamera = useAppSelector((s) => s.ui.frontCamera);
  const backCamera = useAppSelector((s) => s.ui.backCamera);
  const boardCamera = useAppSelector((s) => s.ui.boardCamera);
  const videoAnalyticsActive = useAppSelector((s) => s.ui.videoAnalyticsActive);
  const audioStatus = useAppSelector((s) => s.ui.audioStatus);
  const videoStatus = useAppSelector((s) => s.ui.videoStatus);
  const hasAudioDevices = useAppSelector((s) => s.ui.hasAudioDevices);
  const audioDevicesLoading = useAppSelector((s) => s.ui.audioDevicesLoading);
  const isRecording = useAppSelector((s) => s.ui.isRecording);
  const justStoppedRecording = useAppSelector((s) => s.ui.justStoppedRecording);
  const hasUploadedVideoFiles = useAppSelector((s) => s.ui.hasUploadedVideoFiles);
  const isPlaybackMode = useAppSelector((s) => s.ui.videoPlaybackMode);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    dispatch(loadCameraSettingsFromStorage());
    const stopExistingMonitoring = async () => {
    try {
        console.log('🔄 Stopping any existing monitoring on component mount...');
        await stopMonitoring();
        dispatch(setMonitoringActive(false));
        console.log('✅ Existing monitoring stopped successfully');
      } catch (error) {
        console.log('ℹ️ No existing monitoring to stop (this is normal):', error);
        dispatch(setMonitoringActive(false));
      }
    };
    stopExistingMonitoring();
    
    const checkAudioDevices = async () => {
      try {
        dispatch(setAudioDevicesLoading(true));
        const devices = await getAudioDevices();
        const hasDevices = devices && devices.length > 0;
        dispatch(setHasAudioDevices(hasDevices));
        
        console.log('Audio devices check:', {
          devices,
          count: devices?.length || 0,
          hasDevices
        });
      } catch (error) {
        console.error('Failed to check audio devices:', error);
        dispatch(setHasAudioDevices(false));
      } finally {
        dispatch(setAudioDevicesLoading(false));
      }
    };

    checkAudioDevices();
  }, [dispatch]);

  useEffect(() => {
    if (justStoppedRecording) {
      const timer = setTimeout(() => {
        dispatch(setJustStoppedRecording(false));
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [justStoppedRecording, dispatch]);

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
      setErrorMsg(t('errors.failedToCopyPath'));
    }
  };

  const handleClose = () => setShowToast(false);

  useEffect(() => {
    let interval: number | undefined;
    const shouldRunTimer = isRecording;

    if (shouldRunTimer) {
      interval = window.setInterval(() => setTimer((t) => t + 1), 1000);
    } else if (interval) {
      clearInterval(interval);
    }

    return () => clearInterval(interval);
  }, [isRecording]);

  useEffect(() => {
    if (processingMode && processingMode !== 'microphone') {
      setTimer(0);
    }
  }, [processingMode]);

  const hasVideoCapability = useMemo(() => {
    const hasCameraSettings = Boolean(
      frontCamera?.trim() || 
      backCamera?.trim() || 
      boardCamera?.trim()
    );

    return hasCameraSettings || hasUploadedVideoFiles === true;
  }, [frontCamera, backCamera, boardCamera, hasUploadedVideoFiles]);


    useEffect(() => {
      if (videoStatus === 'completed' || videoStatus === 'failed') return;

      if (hasVideoCapability && videoStatus === 'no-config') {
        dispatch(setVideoStatus('ready'));
      } else if (!hasVideoCapability && videoStatus !== 'no-config') {
        dispatch(setVideoStatus('no-config'));
      }
    }, [hasVideoCapability, videoStatus, dispatch]);

  useEffect(() => {
    switch (audioStatus) {
      case 'checking':
        setAudioNotification(t('notifications.checkingAudioDevices'));
        break;
      case 'no-devices':
        setAudioNotification(t('notifications.noAudioDevices'));
        break;
      case 'ready':
        setAudioNotification(t('notifications.audioReady'));
        break;
      case 'recording':
        setAudioNotification(t('notifications.recording'));
        break;
      case 'processing':
        setAudioNotification(t('notifications.analyzingAudio'));
        break;
      case 'transcribing':
        setAudioNotification(t('notifications.loadingTranscript'));
        break;
      case 'summarizing':
        if (summaryLoading) {
          setAudioNotification(t('notifications.generatingSummary'));
        } else {
          setAudioNotification(t('notifications.streamingSummary'));
        }
        break;
      case 'mindmapping':
        setAudioNotification(t('notifications.generatingMindmap'));
        break;
      case 'complete':
        if (mindmapEnabled && mindmapState.finalText) {
          setAudioNotification(t('notifications.mindmapReady'));
        } else if (summaryEnabled) {
          setAudioNotification(t('notifications.summaryReady'));
        } else {
          setAudioNotification(t('notifications.audioProcessingComplete'));
        }
        break;
      case 'error':
        if (mindmapState.error) {
          setAudioNotification(t('notifications.mindmapError'));
        }
        break;
      default:
        setAudioNotification(t('notifications.audioReady'));
    }
  }, [audioStatus, summaryLoading, mindmapEnabled, mindmapState.finalText, mindmapState.error, summaryEnabled, t]);

  useEffect(() => {
    if (justStoppedRecording && hasVideoCapability) {
      setVideoNotification(t('notifications.videoStreamingStopped'));
      return;
    }

    switch (videoStatus) {
      case 'idle':
      case 'ready':
        setVideoNotification(t('notifications.videoReady'));
        break;
      case 'no-config':
        setVideoNotification(t('notifications.noVideoConfigured'));
        break;
      case 'starting':
        setVideoNotification(t('notifications.startingVideoAnalytics'));
        break;
      case 'streaming':
        setVideoNotification(t('notifications.analyzingVideo'));
        break;
      case 'stopping':
        setVideoNotification(t('notifications.stoppingVideoAnalytics'));
        break;
      case 'failed':
        setVideoNotification(t('notifications.videoAnalyticsFailed'));
        break;
      case 'completed':
        setVideoNotification(
          isPlaybackMode ? t('notifications.playbackMode') : t('notifications.videoStreamingComplete'));
        break;
      default:
        setVideoNotification(hasVideoCapability ? t('notifications.videoReady') : t('notifications.noVideoConfigured'));
    }
  }, [videoStatus, justStoppedRecording, hasVideoCapability, isPlaybackMode, t]);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      setErrorMsg(detail || t('errors.anErrorOccurred'));
    };
    window.addEventListener('global-error', handler as EventListener);
    return () => window.removeEventListener('global-error', handler as EventListener);
  }, [t]);

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

    const hasAudio = Boolean(uploadedAudioPath);
    const hasVideo = hasUploadedVideoFiles;

    const isMindmapDone =
      audioStatus === 'complete' ||
      audioStatus === 'error';

    const areStreamsStopped =
      videoStatus === 'completed' ||
      videoStatus === 'ready' ||
      videoStatus === 'no-config' ||
      videoStatus === 'failed';

    const audioReady = !hasAudio || isMindmapDone;
    const videoReady = !hasVideo || areStreamsStopped;

    const isUploadButtonEnabled = audioReady && videoReady;

    const isUploadDisabled =
      isRecording ||
      !isUploadButtonEnabled;

    const hasLiveCapability =
      hasAudioDevices ||
      Boolean(frontCamera?.trim() || backCamera?.trim() || boardCamera?.trim());

    const isAudioBusy =
      audioStatus === 'processing' ||
      audioStatus === 'transcribing' ||
      audioStatus === 'summarizing' ||
      audioStatus === 'mindmapping';

    const isVideoBusy =
      videoStatus === 'starting' ||
      videoStatus === 'stopping';

    // Recording button should be enabled when recording (so user can stop)
    // or when ready to start recording
    const isRecordingDisabled =
      isRecording ? false : (
        audioDevicesLoading ||
        !hasLiveCapability ||
        isUploading ||
        isAudioBusy ||
        isVideoBusy
      );

  const startVideoAnalyticsInBackground = async (sharedSessionId: string) => {
    if (!videoAnalyticsEnabled) {
      console.log('🎥 Video analytics disabled, skipping');
      return;
    }

    try {
      const currentFrontCamera = frontCamera || '';
      const currentBackCamera = backCamera || '';
      const currentBoardCamera = boardCamera || '';

      if (!currentFrontCamera.trim() && !currentBackCamera.trim() && !currentBoardCamera.trim()) {
        console.log('🎥 No cameras configured in settings, skipping video analytics');
        dispatch(setVideoAnalyticsLoading(false));
        dispatch(setVideoStatus('no-config'));
        return;
      }

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
        dispatch(setVideoAnalyticsLoading(false));
        dispatch(setVideoStatus('no-config'));
        return;
      }
      
      dispatch(startStream());
      dispatch(setVideoAnalyticsLoading(true));
      dispatch(setVideoStatus('starting'));
      
      const videoResult = await startVideoAnalytics(videoRequests, sharedSessionId);
      
      // Start pipeline monitoring for video analytics
      startPipelineMonitoring(sharedSessionId);
      console.log('📹 Video pipeline monitoring started for session:', sharedSessionId);

      if (videoResult && videoResult.results) {
        let hasSuccessfulStreams = false;
        let successfulPipelines: any[] = [];
        let failedPipelines: { name: any; error: any; }[] = [];
        
        console.log('📹 Video analytics response:', videoResult);
        
        videoResult.results.forEach((result: any) => {
          console.log(`📹 Processing result for ${result.pipeline_name}:`, result);
          
          if (result.status === 'success' && result.stream_url) {
            hasSuccessfulStreams = true;
            successfulPipelines.push(result.pipeline_name);
            console.log(`✅ ${result.pipeline_name} stream URL:`, result.stream_url);
            
            switch (result.pipeline_name) {
              case 'front':
                dispatch(setFrontCameraStream(result.stream_url));
                break;
              case 'back':
                dispatch(setBackCameraStream(result.stream_url));
                break;
              case 'content':
                dispatch(setBoardCameraStream(result.stream_url));
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
          dispatch(setVideoPlaybackMode(false));
          dispatch(setVideoAnalyticsActive(true));
          dispatch(setActiveStream('all'));
          dispatch(setVideoStatus('streaming'));
          dispatch(setHasUploadedVideoFiles(true));
          console.log(`🎥 Video analytics started successfully. Working: ${successfulPipelines.join(', ')}`);
          
          if (failedPipelines.length > 0) {
            const failedNames = failedPipelines.map(p => p.name).join(', ');
            console.warn(`⚠️ Some cameras failed: ${failedNames}`);
          }

        } else {
          console.warn('🎥 All video streams failed to start');
          dispatch(setVideoAnalyticsActive(false));
          dispatch(setVideoStatus('failed'));
          dispatch(setHasUploadedVideoFiles(false));
        }
      }
      
    } catch (videoError) {
      console.warn('🎥 Video analytics failed:', videoError);
      dispatch(setVideoAnalyticsActive(false));
      dispatch(setVideoStatus('failed'));
    } finally {
      dispatch(setVideoAnalyticsLoading(false));
    }
  };

  const handleRecordingToggle = async () => {
    if (isRecordingDisabled) return;

    const next = !isRecording;
    clearForNewOp();

    if (next) {
      setTimer(0);
      dispatch(resetFlow());
      dispatch(resetTranscript());
      dispatch(resetSummary());
      dispatch(clearMindmap());
      dispatch(setJustStoppedRecording(false));
      dispatch(startProcessing());
      
      if (hasAudioDevices) {
        dispatch(setProcessingMode('microphone'));
        dispatch(setAudioStatus('recording'));
        console.log('🎙️ Starting recording with microphone');
      } else {
        dispatch(setProcessingMode('video-only' as any));
        dispatch(setAudioStatus('no-devices'));
        console.log('🎥 Starting video-only recording (no audio processing)');
      }

      try {
        const sessionResponse = await createSession();
        const sharedSessionId = sessionResponse.sessionId;
        dispatch(setSessionId(sharedSessionId));
        try {
          if (monitoringActive) {
            await stopMonitoring();
            dispatch(setMonitoringActive(false));
            await new Promise(res => setTimeout(res, 5000));
          }
          console.log('📊 Starting monitoring for new session:', sharedSessionId);
          await startMonitoring(sharedSessionId);
          dispatch(setMonitoringActive(true));
        } catch (monitoringError) {
          console.error('❌ Monitoring restart failed (non-critical):', monitoringError);
        }

        if (hasAudioDevices) {
          dispatch(setUploadedAudioPath('MICROPHONE'));
          dispatch(startTranscription());
          console.log('🎙️ Microphone recording started - transcription will begin automatically');
        } else {
          console.log('🎙️ No audio devices - skipping microphone recording');
        }
        
        dispatch(setIsRecording(true));

        if (hasVideoCapability) {
          console.log('🎥 Starting video analytics with shared session ID...');
          await startVideoAnalyticsInBackground(sharedSessionId);
        } else {
          console.log('🎥 No video streams configured - skipping video analytics');
          dispatch(setVideoStatus('no-config'));
        }
        
      } catch (error) {
        console.error('Failed to start recording:', error);
        setErrorMsg(t('errors.failedToStartRecording'));
        dispatch(processingFailed());
        dispatch(setIsRecording(false));
      }
    } else {
      console.log('🛑 Stopping recording - checking current states...');
      console.log('🔍 Current states:', {
        hasAudioDevices,
        hasVideoCapability,
        audioStatus,
        videoStatus,
        videoAnalyticsActive,
        uploadedAudioPath,
        processingMode
      });

      dispatch(setIsRecording(false));
      dispatch(setJustStoppedRecording(true));
      
      try {
        const wasRecordingAudio = hasAudioDevices && uploadedAudioPath === 'MICROPHONE';
        
        if (sessionId && wasRecordingAudio) {
          console.log('🎙️ Stopping microphone recording...');
          const result = await stopMicrophone(sessionId);
          console.log('🛑 Microphone stopped:', result);
          console.log('🎙️ Audio processing may continue (transcription → summary → mindmap)');
        } else if (!hasAudioDevices) {
          console.log('🎙️ No audio devices - preserving audio status as no-devices');
          dispatch(setAudioStatus('no-devices'));
        } else {
          console.log('🎙️ No microphone recording to stop');
          if (audioStatus === 'recording') {
            dispatch(setAudioStatus(hasAudioDevices ? 'ready' : 'no-devices'));
          }
        }

        const wasVideoActive = videoAnalyticsActive && hasVideoCapability;
        
        if (wasVideoActive && sessionId) {
          try {
            dispatch(setVideoStatus('stopping'));
            dispatch(setVideoAnalyticsStopping(true));
            console.log('🎥 Stopping video analytics...');
            
            const videoRequests = [
              { pipeline_name: 'front' },
              { pipeline_name: 'back' },
              { pipeline_name: 'content' },
            ];

            console.log('🛑 Stopping video analytics with shared session:', sessionId);
            const videoResult = await stopVideoAnalytics(videoRequests, sessionId);
            console.log('🛑 Video analytics stopped:', videoResult);

            // Check for recorded videos and trigger playback mode if available
            let hasRecordedVideo = false;
            try {
              console.log('📹 Checking recorded videos for sessionId:', sessionId);
              const recordedVideos = await checkRecordedVideos(sessionId);
              console.log('📹 Recorded videos check:', recordedVideos);
              
              if (recordedVideos.selected_video) {
                hasRecordedVideo = true;
                console.log(`📹 Found recorded video: ${recordedVideos.selected_video}`);
                console.log('📹 Dispatching setRecordedVideoType:', recordedVideos.selected_video);
                console.log('📹 Current sessionId in dispatch:', sessionId);
                dispatch(setVideoPlaybackMode(true));
                dispatch(setHasUploadedVideoFiles(true));
                dispatch(setRecordedVideoType(recordedVideos.selected_video));
                console.log('🎬 Playback mode enabled for recorded video');
              } else {
                console.log('📹 No recorded videos found');
                dispatch(setVideoPlaybackMode(false));
                dispatch(setHasUploadedVideoFiles(false));
                dispatch(setRecordedVideoType(null));
              }
            } catch (recordCheckError) {
              console.warn('Failed to check recorded videos (non-critical):', recordCheckError);
              dispatch(setVideoPlaybackMode(false));
              dispatch(setHasUploadedVideoFiles(false));
              dispatch(setRecordedVideoType(null));
            }

            dispatch(setFrontCameraStream(''));
            dispatch(setBackCameraStream(''));
            dispatch(setBoardCameraStream(''));
            // Only reset activeStream if NOT in playback mode (so VideoStream's useEffect can set it properly)
            if (!hasRecordedVideo) {
              dispatch(setActiveStream(null));
            }
            dispatch(setVideoAnalyticsActive(false));
            dispatch(setVideoStatus('completed'));
            dispatch(setUploadedVideoFiles({
              front: null,
              back: null,
              board: null,
            }));
            
          } catch (videoError) {
            console.warn('Failed to stop video analytics (non-critical):', videoError);
            dispatch(setVideoAnalyticsActive(false));
            dispatch(setVideoStatus('failed'));
          } finally {
            dispatch(setVideoAnalyticsStopping(false));
            console.log('🛑 Video analytics stopping process completed');
          }
        } else if (!hasVideoCapability) {
          console.log('🎥 No video capability - preserving video status as no-config');
          dispatch(setVideoStatus('no-config'));
        } else {
          console.log('🎥 No active video analytics to stop');
          dispatch(setVideoStatus(hasVideoCapability ? 'ready' : 'no-config'));
          dispatch(setFrontCameraStream(''));
          dispatch(setBackCameraStream(''));
          dispatch(setBoardCameraStream(''));
          dispatch(setActiveStream(null));
          dispatch(setVideoAnalyticsActive(false));
          dispatch(setVideoPlaybackMode(false));
        }
        if (!wasRecordingAudio || !hasAudioDevices) {
          dispatch(setProcessingMode(null));
          console.log('🔄 Processing mode reset');
        } else {
          console.log('🔄 Keeping processing mode - audio processing may continue');
        }
        if (uploadedAudioPath === 'MICROPHONE') {
          if (!wasRecordingAudio) {
            dispatch(setUploadedAudioPath(''));
          } else {
            console.log('🔄 Keeping uploaded audio path - processing continues');
          }
        }

        console.log('✅ Recording stopped gracefully with state preservation');
        
      } catch (error) {
        console.error('Failed to stop recording:', error);
        setErrorMsg(t('errors.failedToStopRecording'));
        dispatch(setVideoAnalyticsStopping(false));
        dispatch(setAudioStatus(hasAudioDevices ? 'ready' : 'no-devices'));
        dispatch(setVideoStatus(hasVideoCapability ? 'ready' : 'no-config'));
        dispatch(setProcessingMode(null));
        dispatch(setUploadedAudioPath(''));
      }
    }
  };

  const getRecordingTooltip = () => {
    if (audioDevicesLoading) return t('tooltips.checkingAudioDevices');
    if (!hasLiveCapability) return t('tooltips.noDevicesOrStreams');
    if (isRecordingDisabled) return t('tooltips.recordingDisabled');
    return isRecording ? t('tooltips.stopRecording') : t('tooltips.startRecording');
  };

  return (
    <div className="header-bar">
      <div className="navbar-left">
        <img
          src={isRecording ? recordON : recordOFF}
          alt="Record"
          className="record-icon"
          onClick={handleRecordingToggle}
          title={getRecordingTooltip()}
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
          title={getRecordingTooltip()}
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
        <NotificationsDisplay 
          audioNotification={audioNotification} 
          videoNotification={videoNotification} 
          error={errorMsg} 
        />
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