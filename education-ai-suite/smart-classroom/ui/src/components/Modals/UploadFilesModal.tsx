import React, { useState } from 'react';
import Modal from './Modal';
import '../../assets/css/UploadFilesModal.css';
import folderIcon from '../../assets/images/folder.svg';
import {
  startVideoAnalyticsPipeline,
  uploadAudio,
  storeAudioDuration,
  createSession,
  startMonitoring,
  stopMonitoring,
  startPipelineMonitoring
} from '../../services/api';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import {
  setUploadedAudioPath,
  startProcessing,
  processingFailed,
  resetFlow,
  setSessionId,
  setActiveStream,
  startStream,
  setFrontCameraStream,
  setBackCameraStream,
  setBoardCameraStream,
  setVideoAnalyticsLoading,
  setVideoAnalyticsActive,
  setProcessingMode,
  setAudioStatus,
  setVideoStatus,
  setHasUploadedVideoFiles,
  setMonitoringActive,
  setUploadedVideoFiles,
} from '../../redux/slices/uiSlice';
import { resetTranscript } from '../../redux/slices/transcriptSlice';
import { resetSummary } from '../../redux/slices/summarySlice';
import { clearMindmap } from '../../redux/slices/mindmapSlice';
import { resetMediaValidation } from '../../redux/slices/mediaValidationSlice';
import { constants } from '../../constants';
import { useTranslation } from 'react-i18next';
interface UploadFilesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const UploadFilesModal: React.FC<UploadFilesModalProps> = ({ isOpen, onClose }) => {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [frontCameraPath, setFrontCameraPath] = useState<File | null>(null);
  const [rearCameraPath, setRearCameraPath] = useState<File | null>(null);
  const [boardCameraPath, setBoardCameraPath] = useState<File | null>(null);
  // Absolute filesystem paths acquired in Electron (empty on the plain web app,
  // where the browser hides the real path and the base directory is used instead).
  const [frontVideoFullPath, setFrontVideoFullPath] = useState<string>('');
  const [rearVideoFullPath, setRearVideoFullPath] = useState<string>('');
  const [boardVideoFullPath, setBoardVideoFullPath] = useState<string>('');
  const [baseDirectory, setBaseDirectory] = useState(() => sessionStorage.getItem('baseDirectory') || "");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(constants.START_NOTIFICATION);
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const monitoringActive = useAppSelector((s) => s.ui.monitoringActive);

  const isElectron = typeof window !== 'undefined' && !!window.electronAPI?.isElectron;

  // In Electron, resolve the file's real absolute path so the backend video
  // pipelines can read it directly. Returns '' on the web (no path setter runs).
  const resolveFullPath = (file: File): string => {
    try {
      return window.electronAPI?.getPathForFile?.(file) ?? '';
    } catch {
      return '';
    }
  };

  // A selected video whose absolute path could not be resolved still needs the
  // base directory (web / fallback).
  const videoMissingFullPath =
    (frontCameraPath !== null && !frontVideoFullPath) ||
    (rearCameraPath !== null && !rearVideoFullPath) ||
    (boardCameraPath !== null && !boardVideoFullPath);
  // Hide the manual base-directory field in Electron once every selected video
  // has a resolved absolute path; keep showing it otherwise (web / fallback).
  const showBaseDirectory = !isElectron || videoMissingFullPath;

  const constructFilePath = (fileName: string): string => {
    const normalizedBaseDirectory = baseDirectory.endsWith("\\") ? baseDirectory : `${baseDirectory}\\`;
    return `${normalizedBaseDirectory}${fileName}`;
  };

  const handleFileSelect = (
    setter: React.Dispatch<React.SetStateAction<File | null>>,
    accept: string,
    pathSetter?: React.Dispatch<React.SetStateAction<string>>
  ) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.onchange = (e: Event) => {
      const target = e.target as HTMLInputElement;
      if (target.files && target.files[0]) {
        const file = target.files[0];
        const fileName = file.name.toLowerCase();
        let isValidFile = false;
        if (accept === '.wav,.mp3,.m4a') {
          isValidFile = fileName.endsWith('.wav') || fileName.endsWith('.mp3') || fileName.endsWith('.m4a');
        } else if (accept === '.mp4') {
          isValidFile = fileName.endsWith('.mp4');
        } else {
          isValidFile = true;
        }

        if (isValidFile) {
          setter(file);
          pathSetter?.(resolveFullPath(file));
          console.log('Selected file:', file);
          setError(null);
        } else {
          setter(null);
          pathSetter?.('');
          const expectedTypes = accept.replace(/\./g, '').replace(/,/g, ', ');
          setError(`Please select only ${expectedTypes} files.`);
        }
      } else {
        setter(null);
        pathSetter?.('');
        console.log('No file selected');
      }
    };
    input.click();
  };

  const startVideoAnalyticsWithSession = async (sessionId: string, pipelines: any[]) => {
    if (pipelines.length === 0) {
      console.log('📹 No valid video pipelines found, skipping video analytics');
      dispatch(setVideoAnalyticsLoading(false));
      dispatch(setVideoAnalyticsActive(false));
      dispatch(setVideoStatus('no-config'));
      return false;
    }

    try {
      console.log('🎬 Starting video analytics with session ID:', sessionId);
      console.log('🎬 Pipelines to send:', pipelines);
      dispatch(startStream());
      dispatch(setVideoAnalyticsLoading(true));
      dispatch(setVideoStatus('starting')); // This will change from 'processed' to 'starting'

      const videoResponse = await startVideoAnalyticsPipeline(pipelines, sessionId);
      startPipelineMonitoring(sessionId);
      let hasSuccessfulStreams = false;

      videoResponse.results.forEach((result: any) => {
        console.log('Processing result:', result);
        if (result.status === "success" && result.stream_url) {
          hasSuccessfulStreams = true;
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
        } else if (result.status === "error") {
          console.error(`❌ Error with ${result.pipeline_name}:`, result.error);
        }
      });

      if (hasSuccessfulStreams) {
        dispatch(setActiveStream('all'));
        dispatch(setVideoAnalyticsActive(true));
        dispatch(setVideoStatus('streaming')); // Only set to streaming when actually streaming
      } else {
        dispatch(setVideoStatus('failed'));
      }

      dispatch(setVideoAnalyticsLoading(false));
      return hasSuccessfulStreams;

    } catch (videoError) {
      console.error('❌ Failed to start video analytics:', videoError);
      dispatch(setVideoAnalyticsLoading(false));
      dispatch(setVideoAnalyticsActive(false));
      dispatch(setVideoStatus('failed'));
      return false;
    }
  };

  const getSuccessNotification = (hasAudio: boolean, hasVideo: boolean, videoStarted: boolean) => {
    const audioSuccess = hasAudio;
    const videoSuccess = hasVideo && videoStarted;

    if (audioSuccess && videoSuccess) {
      return 'Transcription and video analytics started successfully.';
    } else if (audioSuccess && !videoSuccess && hasVideo) {
      return 'Transcription started successfully. Video analytics failed to start.';
    } else if (audioSuccess && !hasVideo) {
      return 'Transcription started successfully.';
    } else if (!audioSuccess && videoSuccess) {
      return 'Video analytics started successfully.';
    } else if (!audioSuccess && !videoSuccess && hasVideo) {
      return 'Failed to start video analytics.';
    } else {
      return 'No valid processing started.';
    }
  };

  const handleApply = async () => {
    const hasAudioFile = audioFile !== null;
    const hasVideoFiles = frontCameraPath !== null || rearCameraPath !== null || boardCameraPath !== null;

    if (!hasAudioFile && !hasVideoFiles) {
      setError('At least one file (audio or video) is required.');
      return;
    }

    // Video pipelines need a full path. In Electron it is acquired automatically;
    // on the web it is reconstructed from the base directory, so require that only
    // for any selected video whose absolute path wasn't resolved.
    if (hasVideoFiles && videoMissingFullPath && !baseDirectory.trim()) {
      setError('Base directory is required when video files are selected.');
      return;
    }

    if (baseDirectory.trim()) {
      sessionStorage.setItem('baseDirectory', baseDirectory);
    }

    setNotification('Starting processing...');
    dispatch(resetFlow());  // Reset flow FIRST
    dispatch(resetTranscript());
    dispatch(resetSummary());
    dispatch(clearMindmap());
    dispatch(resetMediaValidation());  // Reset media validation state
    dispatch(startProcessing());

    // Set uploaded video files AFTER reset to preserve them
    console.log('🎥 Setting uploaded video files in Redux:', {
      front: frontCameraPath ? frontCameraPath.name : 'null',
      back: rearCameraPath ? rearCameraPath.name : 'null',
      board: boardCameraPath ? boardCameraPath.name : 'null'
    });

    dispatch(setUploadedVideoFiles({
      front: frontCameraPath,
      back: rearCameraPath,
      board: boardCameraPath,
    }));

    if (hasAudioFile) {
      dispatch(setAudioStatus('processing'));
      console.log('🎯 Audio status set to processing - will show "Analyzing audio..."');
    } else {
      dispatch(setAudioStatus('no-devices'));
      console.log('🎯 Audio status set to ready - no audio file selected');
    }

    setLoading(true);
    setError(null);

    try {
      setNotification('Creating session...');
      const sessionResponse = await createSession();
      const sessionId = sessionResponse.sessionId;
      console.log('✅ Session created:', sessionId);
      dispatch(setSessionId(sessionId));

      try {
        if (monitoringActive) {
          await stopMonitoring();
          dispatch(setMonitoringActive(false));
          await new Promise(res => setTimeout(res, 5000));
        }
        console.log('📊 Starting monitoring for new session:', sessionId);
        await startMonitoring(sessionId);
        dispatch(setMonitoringActive(true));
      } catch (monitoringError) {
        console.error('❌ Monitoring restart failed:', monitoringError);
      }

      let audioPath = '';
      if (hasAudioFile) {
        const audioResponse = await uploadAudio(audioFile);
        dispatch(setUploadedAudioPath(audioResponse.path));
        audioPath = audioResponse.path;
        console.log('✅ Audio uploaded successfully:', audioResponse);

        // Extract and store audio duration
        try {
          console.log('🔊 Extracting audio duration from file:', audioFile.name);
          await storeAudioDuration(sessionId, audioFile);
          console.log('✅ Audio duration stored successfully');
        } catch (durationError) {
          console.error('⚠️ Failed to store audio duration:', durationError);
        }

        dispatch(setProcessingMode('audio'));
      } else {
        console.log('📝 No audio file provided, skipping audio upload');
        dispatch(setProcessingMode('video-only'));
      }

      console.log('🎥 Video files uploaded:', {
        frontCameraPath: frontCameraPath ? `File: ${frontCameraPath.name}` : 'null',
        rearCameraPath: rearCameraPath ? `File: ${rearCameraPath.name}` : 'null',
        boardCameraPath: boardCameraPath ? `File: ${boardCameraPath.name}` : 'null'
      });

      // Prefer the absolute path acquired in Electron; fall back to the base
      // directory + filename reconstruction used by the plain web app.
      const frontFullPath = frontCameraPath ? (frontVideoFullPath || constructFilePath(frontCameraPath.name)) : "";
      const rearFullPath = rearCameraPath ? (rearVideoFullPath || constructFilePath(rearCameraPath.name)) : "";
      const boardFullPath = boardCameraPath ? (boardVideoFullPath || constructFilePath(boardCameraPath.name)) : "";

      console.log('📹 Constructed file paths for video analytics:', {
        front: frontFullPath,
        rear: rearFullPath,
        board: boardFullPath,
      });

      const allPipelines = [
        {
          pipeline_name: 'front',
          source: frontFullPath
        },
        {
          pipeline_name: 'back',
          source: rearFullPath
        },
        {
          pipeline_name: 'content',
          source: boardFullPath
        },
      ];

      const validPipelines = allPipelines.filter(pipeline =>
        pipeline.source && pipeline.source.trim() !== ''
      );

      const hasValidVideo = validPipelines.length > 0;
      console.log('🎯 Has valid video files:', hasValidVideo);
      dispatch(setHasUploadedVideoFiles(hasValidVideo));

      if (hasValidVideo) {
        console.log('🎥 Setting uploaded video files in Redux (second time, inside video block):', {
          front: frontCameraPath ? frontCameraPath.name : 'null',
          back: rearCameraPath ? rearCameraPath.name : 'null',
          board: boardCameraPath ? boardCameraPath.name : 'null'
        });

        dispatch(setUploadedVideoFiles({
          front: frontCameraPath,
          back: rearCameraPath,
          board: boardCameraPath,
        }));

        dispatch(setHasUploadedVideoFiles(true));

        if (rearCameraPath)
          dispatch(setActiveStream('back'));

        else if (boardCameraPath)
          dispatch(setActiveStream('content'));

        else if (frontCameraPath)
          dispatch(setActiveStream('front'));
      }
      else {
        dispatch(setVideoStatus('no-config'));
      }

      let videoAnalyticsStarted = false;
      if (hasValidVideo) {
        videoAnalyticsStarted = await startVideoAnalyticsWithSession(sessionId, validPipelines);
        if (videoAnalyticsStarted) {
          console.log('✅ Video analytics started successfully');
        } else {
          console.warn('⚠️ Video analytics failed to start');
          dispatch(setVideoStatus('failed'));
        }
      } else {
        console.log('📹 No valid video files provided, skipping video analytics');
      }

      const finalNotification = getSuccessNotification(hasAudioFile, hasValidVideo, videoAnalyticsStarted);

      console.log(finalNotification)
      setNotification(finalNotification);

      console.log('✅ Processing summary:', {
        audioFile: hasAudioFile,
        videoFiles: hasValidVideo,
        videoAnalyticsStarted,
        finalMessage: finalNotification
      });

      setLoading(false);
      onClose();
    } catch (err) {
      console.error('❌ Failed during processing:', err);
      setError('Failed during processing. Please try again.');
      setNotification('');
      dispatch(processingFailed());
      setLoading(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} closeOnOverlayClick={false}>
      <div className="upload-files-modal">
        <h2>{t('uploadFiles.title')}</h2>
        <hr className="modal-title-line" />
        <div className="modal-body">
          {/* The base directory only reconstructs video paths on the plain web
              app; in Electron the full path is acquired automatically, so hide it. */}
          {showBaseDirectory && (
            <div className="modal-input-group">
              <label>{t('uploadFiles.baseDirectoryLabel')}</label>
              <input
                type="text"
                value={baseDirectory}
                onChange={(e) => setBaseDirectory(e.target.value)}
                placeholder="Enter the base directory"
              />
            </div>
          )}
          <div className="modal-input-group modal-title fw-semibold">
            <label>{t('uploadFiles.audioFileLabel')}</label>
            <div className="file-input-wrapper">
              <input
                type="text"
                value={audioFile?.name || ''}
                readOnly
                placeholder="Select an audio file"
              />
              <img
                src={folderIcon}
                alt="Choose File"
                className="folder-icon"
                onClick={() => handleFileSelect(setAudioFile, '.wav,.mp3')}
              />
            </div>
          </div>
          <div className="modal-input-group">
            <label>{t('uploadFiles.frontCameraFile')}</label>
            <div className="file-input-wrapper">
              <input
                type="text"
                value={frontVideoFullPath || frontCameraPath?.name || ''}
                readOnly
                placeholder="Select a front camera file"
                title={frontVideoFullPath || frontCameraPath?.name || ''}
              />
              <img
                src={folderIcon}
                alt="Choose File"
                className="folder-icon"
                onClick={() => handleFileSelect(setFrontCameraPath, '.mp4', setFrontVideoFullPath)}
              />
            </div>
          </div>

          <div className="modal-input-group">
            <label>{t('uploadFiles.backCameraFile')}</label>
            <div className="file-input-wrapper">
              <input
                type="text"
                value={rearVideoFullPath || rearCameraPath?.name || ''}
                readOnly
                placeholder="Select a back camera file"
                title={rearVideoFullPath || rearCameraPath?.name || ''}
              />
              <img
                src={folderIcon}
                alt="Choose File"
                className="folder-icon"
                onClick={() => handleFileSelect(setRearCameraPath, '.mp4', setRearVideoFullPath)}
              />
            </div>
          </div>

          <div className="modal-input-group">
            <label>{t('uploadFiles.boardCameraFile')}</label>
            <div className="file-input-wrapper">
              <input
                type="text"
                value={boardVideoFullPath || boardCameraPath?.name || ''}
                readOnly
                placeholder="Select a board camera file"
                title={boardVideoFullPath || boardCameraPath?.name || ''}
              />
              <img
                src={folderIcon}
                alt="Choose File"
                className="folder-icon"
                onClick={() => handleFileSelect(setBoardCameraPath, '.mp4', setBoardVideoFullPath)}
              />
            </div>
          </div>
          {error && <div className="error-message">{error}</div>}
          {notification && <div className="notification-message">{notification}</div>}
        </div>
        <div className="modal-actions">
          <button
            onClick={handleApply}
            className="apply-button"
            disabled={(!audioFile && !frontCameraPath && !rearCameraPath && !boardCameraPath) || loading}
          >
            {loading ? t('uploadFiles.processing') : t('uploadFiles.applyAndStart')}
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default UploadFilesModal;