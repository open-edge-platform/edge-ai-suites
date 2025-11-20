import React, { useState } from 'react';
import Modal from './Modal';
import '../../assets/css/UploadFilesModal.css';
import folderIcon from '../../assets/images/folder.svg';
import { startVideoAnalyticsPipeline, uploadAudio, getClassStatistics } from '../../services/api';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setFrontCamera, setBackCamera, setBoardCamera, setUploadedAudioPath, startProcessing, processingFailed } from '../../redux/slices/uiSlice';

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

  const dispatch = useAppDispatch();
  const sessionId = useAppSelector((state) => state.ui.sessionId);

  const constructFilePath = (fileName: string): string => {
    return `${baseDirectory}${fileName}`;
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
    if (!audioPath || !frontCameraPath || !rearCameraPath || !boardCameraPath) {
      setError('All file paths are required.');
      return;
    }
  
    setLoading(true);
    setError(null);
  
    try {
      dispatch(startProcessing());
  
      // Construct full file paths for video files
      const frontFullPath = constructFilePath(frontCameraPath.name);
      const rearFullPath = constructFilePath(rearCameraPath.name);
      const boardFullPath = constructFilePath(boardCameraPath.name);
  
      // Construct the payload for all pipelines
      const pipelines = [
        { pipeline_name: 'front', source: frontFullPath },
        { pipeline_name: 'back', source: rearFullPath },
        { pipeline_name: 'content', source: boardFullPath },
      ];
  
      // Trigger both audio and video pipelines in parallel
      const [audioResponse, videoResponse] = await Promise.all([
        uploadAudio(audioPath), // Audio upload remains unchanged
        startVideoAnalyticsPipeline(pipelines, sessionId!), // Send all pipelines in one request
      ]);
  
      // Update Redux state with the uploaded audio path and HLS stream URLs
      dispatch(setUploadedAudioPath(audioResponse.path));
      videoResponse.results.forEach((result: any) => {
        if (result.pipeline_name === 'front') {
          dispatch(setFrontCamera(result.hls_stream));
        } else if (result.pipeline_name === 'back') {
          dispatch(setBackCamera(result.hls_stream));
        } else if (result.pipeline_name === 'content') {
          dispatch(setBoardCamera(result.hls_stream));
        }
      });
  
      // Fetch class statistics after all pipelines are started
      const classStatistics = await getClassStatistics(sessionId!);
      console.log('Class Statistics:', classStatistics);
  
      onClose();
    } catch (err) {
      console.error('Failed to start pipelines:', err);
      setError('Failed to start pipelines. Please try again.');
      dispatch(processingFailed());
    } finally {
      setLoading(false);
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
                value={audioPath?.name || ''}
                readOnly
                placeholder="Select an audio file"
              />
              <img
                src={folderIcon}
                alt="Choose File"
                className="folder-icon"
                onClick={() => handleFileSelect(setAudioPath, 'audio/*')}
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