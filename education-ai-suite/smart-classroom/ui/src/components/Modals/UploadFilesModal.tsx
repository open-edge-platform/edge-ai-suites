import React, { useState, useRef } from 'react';
import Modal from './Modal';
import '../../assets/css/UploadFilesModal.css';
import folderIcon from '../../assets/images/folder.svg';
import { startVideoAnalyticsPipeline, uploadAudio, getClassStatistics, streamTranscript } from '../../services/api';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setFrontCamera, setBackCamera, setBoardCamera, setUploadedAudioPath, startProcessing, processingFailed, resetFlow, setSessionId, setActiveStream, startStream, transcriptionComplete, setFrontCameraStream, setBackCameraStream, setBoardCameraStream, setVideoAnalyticsLoading, setVideoAnalyticsActive } from '../../redux/slices/uiSlice';
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
        setter(file);
        console.log('Selected file:', file);
        setError(null);
      } else {
        // Explicitly set the state to null if no file is selected
        setter(null);
        console.log('No file selected');
      }
    };
    input.click();
  };
 
  const startStreamTranscriptAndVideoAnalytics = (audioPath: string, pipelines: any[]) => {
    const aborter = new AbortController();
    abortRef.current = aborter;
 
    const run = async () => {
      try {
        console.log('🎯 Starting transcript stream for:', audioPath);
       
        const stream = streamTranscript(audioPath, {
          signal: aborter.signal,
          tokenDelayMs: 120,
          onSessionId: async (id) => {
            console.log('🆔 UploadFilesModal received sessionId:', id);
           
            if (!id) {
              console.error('❌ Session ID is null');
              return;
            }
           
            console.log('✅ UploadFilesModal dispatching setSessionId:', id);
            dispatch(setSessionId(id));
           
            // Check if we have any valid video pipelines
            if (pipelines.length > 0) {
              // Start video analytics immediately when we get session ID
              try {
                console.log('🎬 Starting video analytics with session ID:', id);
                console.log('🎬 Pipelines to send:', pipelines);
                dispatch(startStream());
                dispatch(setVideoAnalyticsLoading(true));
               
                const videoResponse = await startVideoAnalyticsPipeline(pipelines, id);
                console.log('✅ Video analytics pipeline started successfully:', videoResponse);

                let hasSuccessfulStreams = false;
   
                // Update Redux state with the results
                videoResponse.results.forEach((result: any) => {
                  console.log('Processing result:', result);
                  if (result.status === "success" && result.hls_stream) {
                    hasSuccessfulStreams = true;
                    switch (result.pipeline_name) {
                      case 'front':
                        console.log('Setting front camera stream:', result.hls_stream);
                        dispatch(setFrontCameraStream(result.hls_stream));
                        break;
                      case 'back':
                        console.log('Setting back camera stream:', result.hls_stream);
                        dispatch(setBackCameraStream(result.hls_stream));
                        break;
                      case 'content':
                        console.log('Setting content camera stream:', result.hls_stream);
                        dispatch(setBoardCameraStream(result.hls_stream));
                        break;
                    }
                  } else if (result.status === "error") {
                    console.error(`❌ Error with ${result.pipeline_name}:`, result.error);
                  }
                });

                if (hasSuccessfulStreams) {
                  // Set active stream to 'all' to show all cameras
                  console.log('Setting active stream to all');
                  dispatch(setActiveStream('all'));
                  dispatch(setVideoAnalyticsActive(true)); // Set video analytics as active
                }
   
                dispatch(setVideoAnalyticsLoading(false));
   
                // Fetch Class Statistics after video analytics starts
                setTimeout(async () => {
                  try {
                    console.log('📊 Fetching class statistics for session:', id);
                    const classStatistics = await getClassStatistics(id);
                    console.log('✅ Class Statistics:', classStatistics);
                    dispatch(setClassStatistics(classStatistics));
                  } catch (err) {
                    console.error('❌ Failed to fetch class statistics:', err);
                  }
                }, 10000);
   
              } catch (videoError) {
                console.error('❌ Failed to start video analytics:', videoError);
                dispatch(setVideoAnalyticsLoading(false));
                dispatch(setVideoAnalyticsActive(false));
              }
            } else {
              console.log('📹 No valid video pipelines found, skipping video analytics');
              // Still set video analytics as inactive but not loading
              dispatch(setVideoAnalyticsLoading(false));
              dispatch(setVideoAnalyticsActive(false));
            }
          },
        });
 
        let sentFirst = false;
        let eventCount = 0;
        console.log('🔄 Starting to process transcript stream...');
       
        for await (const ev of stream) {
          eventCount++;
         
          if (ev.type === "transcript") {
            if (!sentFirst) {
              console.log('🎤 Starting transcript display');
              dispatch(startTranscript());
              sentFirst = true;
            }
            dispatch(appendTranscript(ev.token));
          } else if (ev.type === 'error') {
            console.error('❌ Transcription error:', ev.message);
            dispatch(finishTranscript());
            break;
          } else if (ev.type === 'done') {
            console.log('✅ Transcription completed');
            dispatch(finishTranscript());
            dispatch(transcriptionComplete());
            break;
          }
        }
       
        console.log(`🏁 Stream processing completed. Total events: ${eventCount}`);
       
      } catch (error) {
        const isAbortError = error instanceof Error && error.name === 'AbortError';
        if (isAbortError) {
          console.log('🛑 Stream was aborted');
        } else {
          console.error('❌ Stream transcript error:', error);
        }
      }
    };
 
    run();
  };
 
  const handleApply = async () => {
    if (!audioFile) {
      setError('Audio file is required.');
      return;
    }
 
    console.log('🚀 Starting processing...');
    setNotification('Starting processing...');
    dispatch(resetFlow());
    dispatch(resetTranscript());
    dispatch(resetSummary());
    dispatch(clearMindmap());
    dispatch(startProcessing());
 
    setLoading(true);
    setError(null);
 
    try {
      setNotification('Uploading audio...');
      const audioResponse = await uploadAudio(audioFile);
      dispatch(setUploadedAudioPath(audioResponse.path));
      console.log('✅ Audio uploaded successfully:', audioResponse);
 
      // Construct video file paths
      const frontFullPath = frontCameraPath ? constructFilePath(frontCameraPath.name) : "";
      const rearFullPath = rearCameraPath ? constructFilePath(rearCameraPath.name) : "";
      const boardFullPath = boardCameraPath ? constructFilePath(boardCameraPath.name) : "";
 
      console.log('📹 Video file paths:', {
        front: frontFullPath,
        rear: rearFullPath,
        board: boardFullPath,
      });
 
      // Construct pipelines - only include pipelines with valid sources
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

      // Filter out pipelines with empty sources
      const validPipelines = allPipelines.filter(pipeline => 
        pipeline.source && pipeline.source.trim() !== ''
      );

      console.log('📹 All pipelines:', allPipelines);
      console.log('📹 Valid pipelines to send:', validPipelines);
 
      setNotification('Starting transcription and video analytics...');
     
      // Start both transcript and video analytics (video analytics will start when session ID is received)
      startStreamTranscriptAndVideoAnalytics(audioResponse.path, validPipelines);
     
      console.log('✅ Transcript and video analytics processes started');
      setNotification('Processing started successfully.');
     
      // Mark that we shouldn't abort the stream when modal closes
      shouldAbortRef.current = false;
     
      setLoading(false);
     
      // Close modal immediately after starting processes
      onClose();
 
    } catch (err) {
      console.error('❌ Failed during processing:', err);
      setError('Failed during processing. Please try again.');
      setNotification('');
      dispatch(processingFailed());
      setLoading(false);
      // Keep shouldAbortRef.current = true so stream gets aborted on error
    }
  };
 
  React.useEffect(() => {
    return () => {
      // Only abort if we should abort (i.e., there was an error or unexpected unmount)
      if (abortRef.current && shouldAbortRef.current) {
        console.log('🛑 Aborting stream due to component unmount or error');
        abortRef.current.abort();
      } else if (abortRef.current) {
        console.log('✅ Modal closed normally - stream continues running');
      }
    };
  }, []);
 
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
                onClick={() => handleFileSelect(setAudioFile, 'audio/*')}
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
                onClick={() => handleFileSelect(setFrontCameraPath, 'video/*')}
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
                onClick={() => handleFileSelect(setRearCameraPath, 'video/*')}
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
                onClick={() => handleFileSelect(setBoardCameraPath, 'video/*')}
              />
            </div>
          </div>
          {error && <div className="error-message">{error}</div>}
          {notification && <div className="notification-message">{notification}</div>}
        </div>
        <div className="modal-actions">
          <button onClick={handleApply} className="apply-button" disabled={!audioFile || loading}>
            {loading ? 'Processing...' : 'Apply & Start Processing'}
          </button>
        </div>
      </div>
    </Modal>
  );
};
 
export default UploadFilesModal;