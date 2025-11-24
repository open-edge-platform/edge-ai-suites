import React, { useState } from 'react';
import Modal from './Modal';
import '../../assets/css/UploadFilesModal.css';
import folderIcon from '../../assets/images/folder.svg';
import { startVideoAnalyticsPipeline, uploadAudio, getClassStatistics, streamTranscript } from '../../services/api';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setFrontCamera, setBackCamera, setBoardCamera, setUploadedAudioPath, startProcessing, processingFailed, resetFlow, setSessionId, setActiveStream, startStream, stopStream } from '../../redux/slices/uiSlice';
import { resetTranscript } from '../../redux/slices/transcriptSlice';
import { resetSummary } from '../../redux/slices/summarySlice';
import { clearMindmap } from '../../redux/slices/mindmapSlice';
import { setClassStatistics } from '../../redux/slices/fetchClassStatistics';
import { constants } from '../../constants';
interface UploadFilesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const UploadFilesModal: React.FC<UploadFilesModalProps> = ({ isOpen, onClose }) => {
  const [audioPath, setAudioPath] = useState<File | null>(null);
  const [frontCameraPath, setFrontCameraPath] = useState<File | null>(null);
  const [rearCameraPath, setRearCameraPath] = useState<File | null>(null);
  const [boardCameraPath, setBoardCameraPath] = useState<File | null>(null);
  const [baseDirectory, setBaseDirectory] = useState("C:\\Users\\Default\\Videos\\"); // Default base directory
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [notification, setNotification] = useState(constants.START_NOTIFICATION);

  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((state) => state.ui.sessionId);

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
        setter(file); // Use the File object directly
        console.log('Selected file:', file); // Debugging log
        setError(null); // Clear error when a file is selected
      }
    };
    input.click();
  };
  const handleApply = async () => {
    // Validate that all file paths are selected
    if (!audioFile || !frontCameraPath || !rearCameraPath || !boardCameraPath) {
      setError('All file paths are required.');
      console.log('Validation failed: Missing file paths');
      return;
    }
    console.log('Validation passed: All file paths are selected');
  
    setLoading(true);
    setError(null);
  
    try {
      // Step 1: Upload the audio file
      console.log('Uploading audio file...');
      const audioResponse = await uploadAudio(audioFile); // Upload the audio file
      dispatch(setUploadedAudioPath(audioResponse.path));                                                                                                                                           
      console.log('Audio uploaded successfully:', audioResponse);
  
      // Notify the user that transcription will start automatically
      setNotification('Audio uploaded. Starting transcription...');
      console.log('Starting transcription...');
      const aborter = new AbortController();
      const stream = streamTranscript(audioResponse.path, {
        signal: aborter.signal,
        tokenDelayMs: 120,
        onSessionId: (id) => {
          console.log('Dispatching setSessionId:', id);
          dispatch(setSessionId(id));
        },
      });
    // } catch (err) {
    //   console.error('Failed to upload audio:', err);
    //   setError('Failed to upload audio. Please try again.');
    //   setNotification('');
    //   dispatch(processingFailed());
    //   setLoading(false);
    //   return; // Exit the function if audio upload fails
    // }
  
    // try {
      // Step 2: Wait for sessionId to be available in Redux
      const waitForSessionId = async (): Promise<string> => {
        return new Promise((resolve, reject) => {
          const interval = setInterval(() => {
            const currentSessionId = sessionId;
            if (currentSessionId) {
              clearInterval(interval);
              resolve(currentSessionId);
            }
          }, 500);
  
          setTimeout(() => {
            clearInterval(interval);
            reject(new Error('Session ID not generated within timeout.'));
          }, 30000); // Timeout after 30 seconds
        });
      };
  
      const generatedSessionId = await waitForSessionId();
      console.log('Session ID retrieved:', generatedSessionId);
  
      // Step 3: Construct full file paths for video files
      const frontFullPath = constructFilePath(frontCameraPath.name);
      const rearFullPath = constructFilePath(rearCameraPath.name);
      const boardFullPath = constructFilePath(boardCameraPath.name);
  
      // Step 4: Trigger the video pipeline
      setNotification('Starting video analytics...');
      dispatch(startStream());
      const pipelines = [
        { pipeline_name: 'front', source: frontFullPath },
        { pipeline_name: 'back', source: rearFullPath },
        { pipeline_name: 'content', source: boardFullPath },
      ];
  
      const videoResponse = await startVideoAnalyticsPipeline(pipelines, generatedSessionId);
      console.log('Video analytics pipeline started successfully:', videoResponse);
  
      // Step 5: Update Redux state with the results
      videoResponse.results.forEach((result: any) => {
        if (result.status === 'success' && result.hls_stream) {
          if (result.pipeline_name === 'front') {
            dispatch(setFrontCamera(result.hls_stream));
          } else if (result.pipeline_name === 'back') {
            dispatch(setBackCamera(result.hls_stream));
          } else if (result.pipeline_name === 'content') {
            dispatch(setBoardCamera(result.hls_stream));
          }
        } else {
          // If the pipeline failed or the stream is invalid, set the corresponding state to null
          if (result.pipeline_name === 'front') {
            dispatch(setFrontCamera(""));
          } else if (result.pipeline_name === 'back') {
            dispatch(setBackCamera(""));
          } else if (result.pipeline_name === 'content') {
            dispatch(setBoardCamera(""));
          }
        }
      });
  
      // Step 6: Set the active stream to "all" only if at least one stream is available
      const hasValidStreams = videoResponse.results.some(
        (result: any) => result.status === 'success' && result.hls_stream
      );
      if (hasValidStreams) {
        dispatch(setActiveStream('all'));
      } else {
        setError('No valid streams available. Please check your files and try again.');
        console.log('No valid streams available.');
      }
  
      dispatch(stopStream()); // Indicate that the video pipeline has stopped
      setNotification('Video analytics completed.');
  
      // Step 7: Fetch Class Statistics
      setNotification('Fetching class statistics...');
      try {
        const classStatistics = await getClassStatistics(generatedSessionId);
        console.log('Class Statistics:', classStatistics);
        dispatch(setClassStatistics(classStatistics));
      } catch (err) {
        console.error('Failed to fetch class statistics:', err);
        setError('Failed to fetch class statistics. Please try again.');
      }
  
      setNotification('Processing completed successfully.');
      onClose(); // Close the modal
    } catch (err) {
      console.error('Failed to start video analytics pipeline:', err);
      setError('Failed to start video analytics pipeline. Please try again.');
      setNotification('');
      dispatch(processingFailed());
    } finally {
      setLoading(false); // Ensure loading state is reset
    }
  };

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
        </div>
        <div className="modal-actions">
          <button onClick={handleApply} className="apply-button" disabled={loading}>
            {loading ? 'Processing...' : 'Apply & Start Processing'}
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default UploadFilesModal;


