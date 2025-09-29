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
import { useTranslation } from 'react-i18next';
import { uploadAudio } from '../../services/api';
import Toast from '../common/Toast';

interface HeaderBarProps {
  projectName: string;
  setProjectName: (name: string) => void;
}

const HeaderBar: React.FC<HeaderBarProps> = ({ projectName }) => {
  const [showToast, setShowToast] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [notification, setNotification] = useState(constants.START_NOTIFICATION);
  const { t } = useTranslation();
  const [timer, setTimer] = useState(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const dispatch = useAppDispatch();
  const isBusy = useAppSelector((s) => s.ui.aiProcessing);
  const summaryEnabled = useAppSelector((s) => s.ui.summaryEnabled);
  const summaryLoading = useAppSelector((s) => s.ui.summaryLoading);
  const transcriptStatus = useAppSelector((s) => s.transcript.status);
  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const projectLocation = useAppSelector((state) => state.ui.projectLocation);
  const handleSummaryComplete = () => {
    setShowToast(true); 
  };
  const handleCopy = () => {
    const location = `${projectLocation}/${projectName}/${sessionId}`;
    navigator.clipboard.writeText(location);
    alert('Copied to clipboard!');
  };

  const handleClose = () => {
    setShowToast(false);
  };
  useEffect(() => {
    let interval: number | null = null;
    if (isRecording) {
      interval = window.setInterval(() => setTimer((t) => t + 1), 1000);
    } else if (!isRecording && timer !== 0) {
      if (interval !== null) clearInterval(interval);
    }
    return () => { if (interval !== null) clearInterval(interval); };
  }, [isRecording, timer]);

  useEffect(() => {
    if (summaryEnabled && summaryLoading) setNotification(t('notifications.generatingSummary'));
    else if (summaryEnabled && isBusy && !summaryLoading) setNotification(t('notifications.streamingSummary'));
    else if (isBusy && transcriptStatus === 'streaming') setNotification(t('notifications.loadingTranscript'));
    else if (isBusy && !summaryEnabled) setNotification(t('notifications.analyzingAudio'));
    else if (!isBusy && summaryEnabled) setNotification(t('notifications.summaryReady'));
    else setNotification(t('notifications.start'));
  }, [isBusy, summaryEnabled, summaryLoading, transcriptStatus, t]);
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<string>).detail;
      setErrorMsg(detail || 'Error');
    };
    window.addEventListener('global-error', handler as EventListener);
    return () => window.removeEventListener('global-error', handler as EventListener);
  }, []);
  const clearForNewOp = () => setErrorMsg(null);
  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const handleRecordingToggle = () => {
    if (isBusy && !isRecording) return;
    const next = !isRecording;
    setIsRecording(next);

    if (next) {
      setTimer(0);
      setNotification(t('notifications.recording'));
      dispatch(resetFlow());
      dispatch(resetTranscript());
      dispatch(resetSummary());
    } else {
      setNotification(t('notifications.uploading'));
      dispatch(startProcessing());
    }
  };

  const handleFileUpload = async (file: File) => {
    if (isBusy || isRecording) return;
    clearForNewOp();
    setNotification(t('notifications.uploading'));
    dispatch(resetFlow());
    dispatch(resetTranscript());
    dispatch(resetSummary());
    dispatch(startProcessing());
    try {
      const result = await uploadAudio(file);
      dispatch(setUploadedAudioPath(result.path));
      setNotification(t('notifications.uploadSuccess'));
      setErrorMsg(null); // Clear any previous error
    } catch (e: any) {
      const msg = e?.response?.data?.message || 'Upload failed';
      setNotification(''); // Clear the notification
      setErrorMsg(msg); // Set error message for NotificationsDisplay
      dispatch(processingFailed());
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
          style={{ opacity: isBusy && !isRecording ? 0.5 : 1, cursor: isBusy && !isRecording ? 'not-allowed' : 'pointer' }}
        />
        <img src={sideRecordIcon} alt="Side Record" className="side-record-icon" />
        <span className="timer">{formatTime(timer)}</span>

        <button
          className="text-button"
          onClick={(e) => { e.preventDefault(); }} 
          disabled={true}
          title="Recording disabled"
          style={{ cursor: 'not-allowed', opacity: 0.6 }}
        >
          {isRecording ? t('header.stopRecording') : t('header.startRecording')}
        </button>

    <label
      className="upload-button"
      style={{ opacity: isBusy || isRecording ? 0.6 : 1, cursor: isBusy || isRecording ? 'not-allowed' : 'pointer' }}
    >
      <input
        type="file"
        accept="audio/*"
        style={{ display: 'none' }}
        disabled={isBusy || isRecording}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFileUpload(f);
          e.currentTarget.value = '';
        }}
      />
      {t('header.uploadFile')}
    </label>

      </div>

      <div className="navbar-center">
        <NotificationsDisplay notification={notification} error={errorMsg} />
      </div>

      <div className="navbar-right">
        <ProjectNameDisplay projectName={projectName} />
      </div>
      {showToast && (
        <Toast
          message={`Summary stored at: ${projectLocation}/${projectName}/${sessionId}`}
          onClose={handleClose}
          onCopy={handleCopy}
        />
      )}
    </div>
  );
};

export default HeaderBar;