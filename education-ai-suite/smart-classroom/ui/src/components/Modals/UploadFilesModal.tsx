import React, { useState, useRef } from 'react';
import Modal from './Modal';
import '../../assets/css/UploadFilesModal.css';
import folderIcon from '../../assets/images/folder.svg';
import { 
  startVideoAnalyticsPipeline, 
  uploadAudio, 
  getClassStatistics, 
  streamTranscript, 
  createSession,
  startMonitoring,  
  stopMonitoring    
} from '../../services/api';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { 
  setFrontCamera, 
  setBackCamera, 
  setBoardCamera, 
  setUploadedAudioPath, 
  startProcessing, 
  processingFailed, 
  resetFlow, 
  setSessionId, 
  setActiveStream, 
  startStream, 
  transcriptionComplete, 
  setFrontCameraStream, 
  setBackCameraStream, 
  setBoardCameraStream, 
  setVideoAnalyticsLoading, 
  setVideoAnalyticsActive, 
  setProcessingMode,
  setAudioStatus,
  setVideoStatus,
  startTranscription
} from '../../redux/slices/uiSlice';
import { resetTranscript, appendTranscript, finishTranscript, startTranscript } from '../../redux/slices/transcriptSlice';
import { resetSummary } from '../../redux/slices/summarySlice';
import { clearMindmap } from '../../redux/slices/mindmapSlice';
import { setClassStatistics } from '../../redux/slices/fetchClassStatistics';
import { constants } from '../../constants';
 
interface UploadFilesModalProps {
  isOpen: boolean;
  onClose: () => void;
}
 
const UploadFilesModal: React.FC<UploadFilesModalProps> = ({ isOpen, onClose }) => {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [frontCameraPath, setFrontCameraPath] = useState<File | null>(null);
  const [rearCameraPath, setRearCameraPath] = useState<File | null>(null);
  const [boardCameraPath, setBoardCameraPath] = useState<File | null>(null);
  const [baseDirectory, setBaseDirectory] = useState("C:\\Users\\Default\\Videos\\");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(constants.START_NOTIFICATION);
  const [monitoringTimer, setMonitoringTimer] = useState<number | null>(null);
 
  const dispatch = useAppDispatch();
  const abortRef = useRef<AbortController | null>(null);
  const shouldAbortRef = useRef<boolean>(true);
 
  const constructFilePath = (fileName: string): string => {
    const normalizedBaseDirectory = baseDirectory.endsWith("\\") ? baseDirectory : `${baseDirectory}\\`;
    return `${normalizedBaseDirectory}${fileName}`;
  };
 
  const handleFileSelect = (setter: React.Dispatch<React.SetStateAction<File | null>>, accept: string) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.onchange = (e: Event) => {
      const target = e.target as HTMLInputElement;
      if (target.files && target.files[0]) {
        const file = target.files[0];
        const fileName = file.name.toLowerCase();
        let isValidFile = false;
        if (accept === '.wav,.mp3') {
          isValidFile = fileName.endsWith('.wav') || fileName.endsWith('.mp3');
        } else if (accept === '.mp4') {
          isValidFile = fileName.endsWith('.mp4');
        } else {
          isValidFile = true;
        }
        
        if (isValidFile) {
          setter(file);
          console.log('Selected file:', file);
          setError(null);
        } else {
          setter(null);
          const expectedTypes = accept.replace(/\./g, '').replace(/,/g, ', ');
          setError(`Please select only ${expectedTypes} files.`);
        }
      } else {
        setter(null);
        console.log('No file selected');
      }
    };
    input.click();
  };
 
  const startStreamTranscriptAndVideoAnalytics = (audioPath: string, sessionId: string, pipelines: any[]) => {
    const aborter = new AbortController();
    abortRef.current = aborter;
 
    const run = async () => {
      try {
        console.log('🎯 Starting transcript stream for:', audioPath);
        console.log('🆔 Using session ID:', sessionId);
       
        const stream = streamTranscript(audioPath, sessionId, {
          signal: aborter.signal,
          tokenDelayMs: 120,
        });
 
        let sentFirst = false;
        let eventCount = 0;
        console.log('🔄 Starting to process transcript stream...');
       
        for await (const ev of stream) {
          eventCount++;
         
          if (ev.type === "transcript") {
            if (!sentFirst) {
              dispatch(startTranscript());
              dispatch(startTranscription());
              console.log('🎯 Audio status updated to transcribing - will show "Loading transcript..."');
              sentFirst = true;
            }
            dispatch(appendTranscript(ev.token));
          } else if (ev.type === 'error') {
            console.error('❌ Transcription error:', ev.message);
            dispatch(finishTranscript());
            dispatch(setAudioStatus('error'));
            break;
          } else if (ev.type === 'done') {
            console.log('✅ Transcription completed');
            dispatch(finishTranscript());
            dispatch(transcriptionComplete());
            break;
          }
        }
      } catch (error) {
        const isAbortError = error instanceof Error && error.name === 'AbortError';
        if (isAbortError) {
          console.log('🛑 Stream was aborted');
        } else {
          console.error('❌ Stream transcript error:', error);
          dispatch(setAudioStatus('error'));
        }
      }
    };
 
    run();
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
      dispatch(setVideoStatus('starting'));
     
      const videoResponse = await startVideoAnalyticsPipeline(pipelines, sessionId);
 
      let hasSuccessfulStreams = false;
 
      videoResponse.results.forEach((result: any) => {
        console.log('Processing result:', result);
        if (result.status === "success" && result.hls_stream) {
          hasSuccessfulStreams = true;
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
        } else if (result.status === "error") {
          console.error(`❌ Error with ${result.pipeline_name}:`, result.error);
        }
      });
 
      if (hasSuccessfulStreams) {
        dispatch(setActiveStream('all'));
        dispatch(setVideoAnalyticsActive(true));
        dispatch(setVideoStatus('streaming'));
      } else {
        dispatch(setVideoStatus('failed'));
      }
 
      dispatch(setVideoAnalyticsLoading(false));
 
      if (hasSuccessfulStreams) {
        setTimeout(async () => {
          try {
            console.log('📊 Fetching class statistics for session:', sessionId);
            const classStatistics = await getClassStatistics(sessionId);
            console.log('✅ Class Statistics:', classStatistics);
            dispatch(setClassStatistics(classStatistics));
          } catch (err) {
            console.error('❌ Failed to fetch class statistics:', err);
          }
        }, 10000);
      }
 
      return hasSuccessfulStreams;
 
    } catch (videoError) {
      console.error('❌ Failed to start video analytics:', videoError);
      dispatch(setVideoAnalyticsLoading(false));
      dispatch(setVideoAnalyticsActive(false));
      dispatch(setVideoStatus('failed'));
      return false;
    }
  };
 
  const getProcessingNotification = (hasAudio: boolean, hasVideo: boolean) => {
    if (hasAudio && hasVideo) {
      return 'Starting video analytics and transcription...';
    } else if (hasAudio && !hasVideo) {
      return 'Starting transcription...';
    } else if (!hasAudio && hasVideo) {
      return 'Starting video analytics...';
    } else {
      return 'Starting processing...';
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

    setNotification('Starting processing...');
    dispatch(resetFlow());
    dispatch(resetTranscript());
    dispatch(resetSummary());
    dispatch(clearMindmap());
    dispatch(startProcessing());

    if (hasAudioFile) {
      dispatch(setAudioStatus('processing'));
      console.log('🎯 Audio status set to processing - will show "Analyzing audio..."');
    } else {
      dispatch(setAudioStatus('no-devices'));
      console.log('🎯 Audio status set to no-devices - will show "No audio devices"');
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
        console.log('📊 Starting monitoring for session:', sessionId);
        const monitoringResult = await startMonitoring(sessionId);
        const timer = setTimeout(async () => {
          try {
            console.log('⏰ 45 minutes elapsed - stopping monitoring');
            const stopResult = await stopMonitoring();
            console.log('✅ Monitoring stopped after 45 minutes:', stopResult.message);
          } catch (error) {
            console.error('❌ Failed to stop monitoring after 45 minutes:', error);
          }
        }, 45 * 60 * 1000);

        setMonitoringTimer(timer);
        console.log('⏰ Monitoring timer set for 45 minutes');
      } catch (monitoringError) {
        console.error('❌ Failed to start monitoring (non-critical):', monitoringError);
      }

      let audioPath = '';
      if (hasAudioFile) {
        setNotification('Uploading...');
        const audioResponse = await uploadAudio(audioFile);
        dispatch(setUploadedAudioPath(audioResponse.path));
        // Audio status already set to 'processing' above
        audioPath = audioResponse.path;
        console.log('✅ Audio uploaded successfully:', audioResponse);
        dispatch(setProcessingMode('audio'));
      } else {
        console.log('📝 No audio file provided, skipping audio upload');
        dispatch(setProcessingMode('video-only'));
        // Audio status already set to 'no-devices' above
      }

      const frontFullPath = frontCameraPath ? constructFilePath(frontCameraPath.name) : "";
      const rearFullPath = rearCameraPath ? constructFilePath(rearCameraPath.name) : "";
      const boardFullPath = boardCameraPath ? constructFilePath(boardCameraPath.name) : "";

      console.log('📹 Video file paths:', {
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

      console.log('📹 All pipelines:', allPipelines);
      console.log('📹 Valid pipelines to send:', validPipelines);

      const hasValidVideo = validPipelines.length > 0;
      console.log('🎯 Has valid video:', hasAudioFile);
      setNotification(getProcessingNotification(hasAudioFile, hasValidVideo));
    
      let videoAnalyticsStarted = false;
      if (hasValidVideo) {
        videoAnalyticsStarted = await startVideoAnalyticsWithSession(sessionId, validPipelines);
        if (videoAnalyticsStarted) {
          console.log('✅ Video analytics started successfully');
        } else {
          console.warn('⚠️ Video analytics failed to start');
        }
      } else {
        console.log('📹 No valid video files provided, skipping video analytics');
        if (hasVideoFiles) {
          dispatch(setVideoStatus('failed'));
        } else {
          dispatch(setVideoStatus('no-config'));
        }
      }
    
      if (hasAudioFile && audioPath) {
        console.log('🎯 Starting transcript stream - audio status will change from processing to transcribing');
        startStreamTranscriptAndVideoAnalytics(audioPath, sessionId, validPipelines);
        console.log('✅ Transcript stream started');
      } else {
        console.log('📝 No audio file provided, skipping transcription');
      }
      console.log(hasAudioFile.valueOf());
      const finalNotification = getSuccessNotification(hasAudioFile, hasValidVideo, videoAnalyticsStarted);
  
      console.log(finalNotification)
      setNotification(finalNotification);
    
      console.log('✅ Processing summary:', {
        audioFile: hasAudioFile,
        videoFiles: hasValidVideo,
        videoAnalyticsStarted,
        finalMessage: finalNotification
      });
    
      shouldAbortRef.current = false;
      setLoading(false);
      onClose();

    } catch (err) {
      console.error('❌ Failed during processing:', err);
      setError('Failed during processing. Please try again.');
      setNotification('');
      dispatch(processingFailed());
      setLoading(false);

      if (monitoringTimer) {
        clearTimeout(monitoringTimer);
        setMonitoringTimer(null);

        try {
          await stopMonitoring();
          console.log('🧹 Monitoring stopped due to error cleanup');
        } catch (stopError) {
          console.error('❌ Failed to stop monitoring during error cleanup:', stopError);
        }
      }
    }
  };

  React.useEffect(() => {
    return () => {
      if (monitoringTimer) {
        clearTimeout(monitoringTimer);
        stopMonitoring().catch(error => {
          console.error('❌ Failed to stop monitoring during cleanup:', error);
        });
      }
      
      if (abortRef.current && shouldAbortRef.current) {
        console.log('🛑 Aborting stream due to component unmount or error');
        abortRef.current.abort();
      } else if (abortRef.current) {
        console.log('✅ Modal closed normally - stream continues running');
      }
    };
  }, [monitoringTimer]);
 
  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <div className="upload-files-modal">
        <h2>Upload Files</h2>
        <hr className="modal-title-line" />
        <div className="modal-body">
          <div className="modal-input-group">
            <label>Base Directory for Video Files</label>
            <input
              type="text"
              value={baseDirectory}
              onChange={(e) => setBaseDirectory(e.target.value)}
              placeholder="Enter the base directory"
            />
          </div>
          <div className="modal-input-group">
            <label>Audio File</label>
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
            <label>Front Camera File</label>
            <div className="file-input-wrapper">
              <input
                type="text"
                value={frontCameraPath?.name || ''}
                readOnly
                placeholder="Select a front camera file"
              />
              <img
                src={folderIcon}
                alt="Choose File"
                className="folder-icon"
                onClick={() => handleFileSelect(setFrontCameraPath, '.mp4')}
              />
            </div>
          </div>

          <div className="modal-input-group">
            <label>Rear Camera File</label>
            <div className="file-input-wrapper">
              <input
                type="text"
                value={rearCameraPath?.name || ''}
                readOnly
                placeholder="Select a rear camera file"
              />
              <img
                src={folderIcon}
                alt="Choose File"
                className="folder-icon"
                onClick={() => handleFileSelect(setRearCameraPath, '.mp4')}
              />
            </div>
          </div>

          <div className="modal-input-group">
            <label>Board Camera File</label>
            <div className="file-input-wrapper">
              <input
                type="text"
                value={boardCameraPath?.name || ''}
                readOnly
                placeholder="Select a board camera file"
              />
              <img
                src={folderIcon}
                alt="Choose File"
                className="folder-icon"
                onClick={() => handleFileSelect(setBoardCameraPath, '.mp4')}
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
            {loading ? 'Processing...' : 'Apply & Start Processing'}
          </button>
        </div>
      </div>
    </Modal>
  );
};
 
export default UploadFilesModal;