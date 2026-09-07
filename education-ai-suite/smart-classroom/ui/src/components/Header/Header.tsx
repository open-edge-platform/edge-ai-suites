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
  setFrontCamera,
  setBackCamera,
  setBoardCamera,
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
import StartRecordingModal from '../Modals/StartRecordingModal';
import type { CameraUrls } from '../../services/cameraStorage';
import {
  usesCameras,
  usesMicrophone,
  type RecordingSettings,
} from '../../services/recordingSettings';
import type { FeatureGuard } from '../../utils/featureGuards';
import { collectPipelineErrors, isNotRunning } from '../../utils/pipelineErrors';
import { usePipelineGate, uploadBlockerTooltipKey } from '../../hooks/usePipelineGate';

// How long a non-fatal error stays in the notification bar before the regular
// audio/video status takes the space back.
const TRANSIENT_ERROR_MS = 15000;

interface HeaderBarProps {
  projectName: string;
  setProjectName: (name: string) => void;
  featureGuard: FeatureGuard;
}

const HeaderBar: React.FC<HeaderBarProps> = ({ projectName, featureGuard }) => {
  const [showToast, setShowToast] = useState(false);
  const [audioNotification, setAudioNotification] = useState('');
  const [videoNotification, setVideoNotification] = useState('');
  const { t } = useTranslation();
  const [timer, setTimer] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [videoAnalyticsEnabled] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isRecordModalOpen, setIsRecordModalOpen] = useState(false);
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
  const frontCameraStream = useAppSelector((s) => s.ui.frontCameraStream);
  const backCameraStream = useAppSelector((s) => s.ui.backCameraStream);
  const boardCameraStream = useAppSelector((s) => s.ui.boardCameraStream);
  const audioStatus = useAppSelector((s) => s.ui.audioStatus);
  const videoStatus = useAppSelector((s) => s.ui.videoStatus);
  const hasAudioDevices = useAppSelector((s) => s.ui.hasAudioDevices);
  const audioDevicesLoading = useAppSelector((s) => s.ui.audioDevicesLoading);
  const isRecording = useAppSelector((s) => s.ui.isRecording);
  const justStoppedRecording = useAppSelector((s) => s.ui.justStoppedRecording);
  const hasUploadedVideoFiles = useAppSelector((s) => s.ui.hasUploadedVideoFiles);
  const isPlaybackMode = useAppSelector((s) => s.ui.videoPlaybackMode);
  const { audioBusy, videoBusy, isUploadEnabled, blocker: uploadBlocker } = usePipelineGate();

  // Check if video_analytics feature is enabled in backend
  const hasVideoAnalyticsFeature = featureGuard.hasFeature('video_analytics');
  
  // Check if audio features are enabled
  const hasAudioFeatures = featureGuard.hasFeature('asr') ||
                           featureGuard.hasFeature('summary') ||
                           featureGuard.hasFeature('mindmap') ||
                           featureGuard.hasFeature('topic_segmentation') ||
                           featureGuard.hasFeature('report');

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
    
    // Only check audio devices if audio features are enabled
    const hasAudioFeatures = featureGuard.hasFeature('asr') ||
                             featureGuard.hasFeature('summary') ||
                             featureGuard.hasFeature('mindmap');
    
    if (hasAudioFeatures) {
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
    }
  }, [dispatch, featureGuard]);

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

  /**
   * Report a failure that does not stop the session — a single camera pipeline,
   * say, while transcription keeps running. The banner hides the audio/video
   * status while it shows, so it steps aside again instead of sticking until the
   * next start/stop. A newer message is never cleared by an older timer.
   */
  const showTransientError = (message: string) => {
    setErrorMsg(message);
    window.setTimeout(
      () => setErrorMsg((current) => (current === message ? null : current)),
      TRANSIENT_ERROR_MS
    );
  };
  
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
    // Video capability requires BOTH backend feature AND config/uploads
    if (!hasVideoAnalyticsFeature) {
      return false;
    }
    
    const hasCameraSettings = Boolean(
      frontCamera?.trim() || 
      backCamera?.trim() || 
      boardCamera?.trim()
    );

    return hasCameraSettings || hasUploadedVideoFiles === true;
  }, [frontCamera, backCamera, boardCamera, hasUploadedVideoFiles, hasVideoAnalyticsFeature]);


    useEffect(() => {
      if (videoStatus === 'completed' || videoStatus === 'failed') return;

      if (hasVideoCapability && videoStatus === 'no-config') {
        dispatch(setVideoStatus('ready'));
      } else if (!hasVideoCapability && videoStatus !== 'no-config') {
        dispatch(setVideoStatus('no-config'));
      }
    }, [hasVideoCapability, videoStatus, dispatch]);

  useEffect(() => {
    // Only set audio notifications if audio features are enabled
    if (!hasAudioFeatures) {
      setAudioNotification('');
      return;
    }
    
    switch (audioStatus) {
      case 'checking':
        setAudioNotification(t('notifications.checkingAudioDevices'));
        break;
      case 'no-devices':
        setAudioNotification(t('notifications.noAudioDevices'));
        break;
      case 'off':
        setAudioNotification(t('notifications.audioOff', 'Audio not recorded'));
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
  }, [audioStatus, summaryLoading, mindmapEnabled, mindmapState.finalText, mindmapState.error, summaryEnabled, t, hasAudioFeatures]);

  useEffect(() => {
    // Only set video notifications if video analytics feature is enabled
    if (!hasVideoAnalyticsFeature) {
      setVideoNotification('');
      return;
    }
    
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
  }, [videoStatus, justStoppedRecording, hasVideoCapability, isPlaybackMode, hasVideoAnalyticsFeature, t]);

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

    // Blocked only while something is actually running (see usePipelineGate) —
    // never on a settled state the gate forgot to list.
    const isUploadDisabled = !isUploadEnabled;

    // Enabled while recording so the user can stop — which is why this reads
    // audioBusy/videoBusy rather than the gate's `blocker`, whose 'recording'
    // case would disable the only way out.
    //
    // When idle it only opens the modal, so it must stay clickable with nothing
    // configured yet — that modal is where a microphone and camera URLs are
    // chosen, and it does the "is there anything to record with?" check on its
    // own Start button.
    const isRecordingDisabled =
      isRecording ? false : (
        audioDevicesLoading ||
        audioBusy ||
        videoBusy
      );

  // The cameras are passed in rather than read from Redux: the start path
  // dispatches resetFlow() first, so anything read from the closure here would
  // be a render behind whatever the user just typed in the modal.
  const startVideoAnalyticsInBackground = async (sharedSessionId: string, cameras: CameraUrls) => {
    if (!videoAnalyticsEnabled) {
      console.log('🎥 Video analytics disabled, skipping');
      return;
    }

    try {
      const currentFrontCamera = cameras.front || '';
      const currentBackCamera = cameras.back || '';
      const currentBoardCamera = cameras.board || '';

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
        const successfulPipelines: any[] = [];
        const failedPipelines: { name: any; error: any; }[] = [];
        
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

        // Per-camera failures come back with HTTP 200, so nothing throws.
        // Show the reasons, including when only some cameras are down.
        const pipelineErrors = collectPipelineErrors(
          videoResult.results,
          t,
          t('notifications.videoAnalyticsFailed')
        );
        if (pipelineErrors.length > 0) {
          showTransientError(t('errors.videoPipelineFailed', { details: pipelineErrors.join('\n') }));
        }

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

  // Pressing the button while recording stops immediately; otherwise it opens
  // the modal, which collects the microphone and camera URLs and calls
  // startRecording with them.
  const handleRecordClick = () => {
    if (isRecordingDisabled) return;
    if (isRecording) {
      void stopRecording();
      return;
    }
    clearForNewOp();
    setIsRecordModalOpen(true);
  };

  /**
   * @param report Names the stage in flight, for the modal that stays open
   *   until this resolves. Bringing a session up takes seconds — a monitoring
   *   handover alone sleeps 5 — and the pipelines are not live until the last
   *   await returns, so the modal is where that wait has to be visible.
   */
  const startRecording = async (settings: RecordingSettings, report: (message: string) => void) => {
    const cameras: CameraUrls = {
      front: settings.front,
      back: settings.back,
      board: settings.board,
    };

    clearForNewOp();
    setTimer(0);
    dispatch(resetFlow());
    dispatch(resetTranscript());
    dispatch(resetSummary());
    dispatch(clearMindmap());
    dispatch(setJustStoppedRecording(false));
    dispatch(startProcessing());
    // After resetFlow, which restores the previous cameras — these are the
    // ones the user just confirmed, so they have to land on top of it.
    dispatch(setFrontCamera(cameras.front));
    dispatch(setBackCamera(cameras.back));
    dispatch(setBoardCamera(cameras.board));

    // What this session actually uses, from what was confirmed in the modal —
    // not from whether the machine happens to have a microphone. Either input
    // alone is a valid session, so both are decided independently.
    const withMic = usesMicrophone({ hasAudioFeatures, microphone: settings.microphone });
    const withCameras = usesCameras({ hasVideoAnalyticsFeature, cameras });

    if (withMic) {
      dispatch(setProcessingMode('microphone'));
      dispatch(setAudioStatus('recording'));
      console.log('🎙️ Starting recording with microphone');
    } else {
      dispatch(setProcessingMode('video-only' as any));
      // Distinguish "this machine has no microphone" from "the user chose not to
      // record audio"; the status bar says something different for each.
      dispatch(setAudioStatus(hasAudioDevices ? 'off' : 'no-devices'));
      console.log('🎥 Starting video-only recording (no audio processing)');
    }

    try {
      report(t('startRecording.creatingSession', 'Creating session…'));
      const sessionResponse = await createSession();
      const sharedSessionId = sessionResponse.sessionId;
      dispatch(setSessionId(sharedSessionId));
      try {
        // Covers the handover as a whole: the stop, the 5s settle and the start.
        report(t('startRecording.startingMonitoring', 'Starting resource monitoring…'));
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

      if (withMic) {
        dispatch(setUploadedAudioPath('MICROPHONE'));
        dispatch(startTranscription());
        console.log('🎙️ Microphone recording started - transcription will begin automatically');
      } else {
        console.log('🎙️ Not recording audio this session - skipping microphone');
      }

      dispatch(setIsRecording(true));

      // hasVideoCapability is derived from Redux and so is a render behind the
      // values just confirmed; ask the confirmed ones instead.
      if (withCameras) {
        console.log('🎥 Starting video analytics with shared session ID...');
        report(t('startRecording.startingVideo', 'Starting video analytics…'));
        await startVideoAnalyticsInBackground(sharedSessionId, cameras);
      } else {
        console.log('🎥 No video streams configured - skipping video analytics');
        dispatch(setVideoStatus('no-config'));
      }

    } catch (error) {
      console.error('Failed to start recording:', error);
      setErrorMsg(t('errors.failedToStartRecording'));
      dispatch(processingFailed());
      dispatch(setIsRecording(false));
      // Rethrown after the cleanup: the modal is still open and covering this
      // banner, so it is the surface that has to report the failure — and it
      // stays open, with Start live again, rather than closing on an error.
      throw error;
    }
  };

  const stopRecording = async () => {
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
      // The start path sets this exactly when it opened the microphone, so it
      // records what actually happened. hasAudioDevices only says what the
      // machine has, which can differ — a camera-only session on a laptop with a
      // built-in mic, or a device list that changed mid-session.
      const wasRecordingAudio = uploadedAudioPath === 'MICROPHONE';

      if (sessionId && wasRecordingAudio) {
        console.log('🎙️ Stopping microphone recording...');
        const result = await stopMicrophone(sessionId);
        console.log('🛑 Microphone stopped:', result);
        console.log('🎙️ Audio processing may continue (transcription → summary → mindmap)');
      } else if (!hasAudioDevices) {
        console.log('🎙️ No audio devices - preserving audio status as no-devices');
        dispatch(setAudioStatus('no-devices'));
      } else {
        // Audio was left out of this session on purpose; say so rather than
        // claiming the machine has no microphone.
        console.log('🎙️ No microphone recording to stop');
        if (audioStatus === 'recording') dispatch(setAudioStatus('ready'));
      }

      const wasVideoActive = videoAnalyticsActive && hasVideoCapability;
      
      if (wasVideoActive && sessionId) {
        try {
          dispatch(setVideoStatus('stopping'));
          dispatch(setVideoAnalyticsStopping(true));
          console.log('🎥 Stopping video analytics...');
          
          // Ask only for the cameras that are actually streaming; the backend
          // answers "is not running" for the rest, which reads as a failure.
          // Fall back to all three if no stream URL is known, so a pipeline is
          // never left running because of stale state.
          const streaming = [
            frontCameraStream && { pipeline_name: 'front' },
            backCameraStream && { pipeline_name: 'back' },
            boardCameraStream && { pipeline_name: 'content' },
          ].filter(Boolean) as Array<{ pipeline_name: string }>;

          const videoRequests = streaming.length > 0 ? streaming : [
            { pipeline_name: 'front' },
            { pipeline_name: 'back' },
            { pipeline_name: 'content' },
          ];

          console.log('🛑 Stopping video analytics with shared session:', sessionId);
          const videoResult = await stopVideoAnalytics(videoRequests, sessionId);
          console.log('🛑 Video analytics stopped:', videoResult);

          // Like the start endpoint, failures to stop come back with HTTP 200.
          // "Not running" is expected housekeeping, so only report the rest.
          const stopErrors = collectPipelineErrors(
            videoResult?.results,
            t,
            t('errors.failedToStopRecording'),
            isNotRunning
          );
          if (stopErrors.length > 0) {
            showTransientError(t('errors.videoPipelineStopFailed', { details: stopErrors.join('\n') }));
          }

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
      // Transcription, summary and mindmap keep running after the microphone
      // closes, so both of these stay put while that is still in flight.
      if (wasRecordingAudio) {
        console.log('🔄 Keeping processing mode and audio path - processing continues');
      } else {
        dispatch(setProcessingMode(null));
        console.log('🔄 Processing mode reset');
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
  };

  const getRecordingTooltip = () => {
    if (audioDevicesLoading) return t('tooltips.checkingAudioDevices');
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
          onClick={handleRecordClick}
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
          onClick={handleRecordClick}
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
          title={t(uploadBlockerTooltipKey(uploadBlocker))}
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
        <UploadFilesModal isOpen={isUploadModalOpen} onClose={handleCloseUploadModal} featureGuard={featureGuard} />
      )}
      {isRecordModalOpen && (
        <StartRecordingModal
          isOpen={isRecordModalOpen}
          onClose={() => setIsRecordModalOpen(false)}
          featureGuard={featureGuard}
          onStart={startRecording}
        />
      )}
    </div>
  );
};

export default HeaderBar;