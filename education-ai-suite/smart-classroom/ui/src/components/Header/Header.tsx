import React, { useState, useEffect } from 'react';
import NotificationsDisplay from '../Display/NotificationsDisplay';
import ProjectNameDisplay from '../Display/ProjectNameDisplay';
import '../../assets/css/HeaderBar.css';
import recordON from '../../assets/images/recording-on.svg';
import recordOFF from '../../assets/images/recording-off.svg';
import sideRecordIcon from '../../assets/images/sideRecord.svg';
import { constants } from '../../constants';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { resetFlow, startProcessing, setUploadedAudioPath, processingFailed } from '../../redux/slices/uiSlice';
import { resetTranscript } from '../../redux/slices/transcriptSlice';
import { resetSummary } from '../../redux/slices/summarySlice';
import { clearMindmap } from '../../redux/slices/mindmapSlice';
import { useTranslation } from 'react-i18next';
import { uploadAudio, stopMicrophone, getAudioDevices } from '../../services/api';
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

  const dispatch = useAppDispatch();
  const isBusy = useAppSelector((s) => s.ui.aiProcessing);
  const summaryEnabled = useAppSelector((s) => s.ui.summaryEnabled);
  const summaryLoading = useAppSelector((s) => s.ui.summaryLoading);
  const transcriptStatus = useAppSelector((s) => s.transcript.status);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false); 

  const handleOpenUploadModal = () => {
    setIsUploadModalOpen(true); // Open the UploadFilesModal
  };

  const handleCloseUploadModal = () => {
    setIsUploadModalOpen(false); // Close the UploadFilesModal
  };
  const mindmapEnabled = useAppSelector((s) => s.ui.mindmapEnabled);
  const mindmapLoading = useAppSelector((s) => s.ui.mindmapLoading);
  const sessionId = useAppSelector((s) => s.ui.sessionId);
  const projectLocation = useAppSelector((s) => s.ui.projectLocation);
  const mindmapState = useAppSelector((s) => s.mindmap);

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

  const isRecordingDisabled =
    isBusy ||
    transcriptStatus === 'streaming' ||     
    summaryLoading ||                         
    (mindmapEnabled && (
      mindmapLoading ||
      mindmapState.isLoading ||
      !mindmapState.finalText                
    )) ||
    !hasAudioDevices;                         

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
        
      } catch (error) {
        console.error('Failed to start microphone:', error);
        setErrorMsg('Failed to start microphone recording');
        dispatch(processingFailed());
        setIsRecording(false);
      }
    } else {
      setIsRecording(false);
      
      try {
        if (sessionId) {
          const result = await stopMicrophone(sessionId);
          console.log('🛑 Microphone stopped:', result);
        } else {
          console.warn('No session ID available to stop microphone');
        }
      } catch (error) {
        console.error('Failed to stop microphone:', error);
        setErrorMsg('Failed to stop microphone recording');
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