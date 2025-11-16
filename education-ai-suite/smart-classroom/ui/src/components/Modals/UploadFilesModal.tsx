import React, { useState } from 'react';
import Modal from './Modal';
import AudioPathInput from '../Inputs/AudioPathInput';
import FrontCameraPathInput from '../Inputs/FrontCameraPathInput';
import RearCameraPathInput from '../Inputs/RearCameraPathInput';
import BoardCameraPathInput from '../Inputs/BoardCameraPathInput';

interface UploadFilesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: (paths: {
    audioPath: string;
    frontCameraPath: string;
    rearCameraPath: string;
    boardCameraPath: string;
  }) => void;
}

const UploadFilesModal: React.FC<UploadFilesModalProps> = ({ isOpen, onClose, onApply }) => {
  const [audioPath, setAudioPath] = useState('');
  const [frontCameraPath, setFrontCameraPath] = useState('');
  const [rearCameraPath, setRearCameraPath] = useState('');
  const [boardCameraPath, setBoardCameraPath] = useState('');

  const handleFolderClick = (type: string) => {
    // Logic to handle folder selection (if applicable)
    console.log(`Folder selection clicked for: ${type}`);
  };

  const handleApply = () => {
    onApply({
      audioPath,
      frontCameraPath,
      rearCameraPath,
      boardCameraPath,
    });
    onClose(); // Close the modal after applying
  };

  return (
    <Modal isOpen={isOpen}>
      <div className="modal-content">
        <h2>Upload Files</h2>
        <div>
          <label>Audio</label>
          <AudioPathInput
            audioPath={audioPath}
            onChange={setAudioPath}
            onFolderClick={() => handleFolderClick('audio')}
          />
        </div>
        <div>
          <label>Front Camera</label>
          <FrontCameraPathInput
            frontCameraPath={frontCameraPath}
            onChange={setFrontCameraPath}
            onFolderClick={() => handleFolderClick('frontCamera')}
          />
        </div>
        <div>
          <label>Rear Camera</label>
          <RearCameraPathInput
            rearCameraPath={rearCameraPath}
            onChange={setRearCameraPath}
            onFolderClick={() => handleFolderClick('rearCamera')}
          />
        </div>
        <div>
          <label>Board Camera</label>
          <BoardCameraPathInput
            boardCameraPath={boardCameraPath}
            onChange={setBoardCameraPath}
            onFolderClick={() => handleFolderClick('boardCamera')}
          />
        </div>
        <div className="modal-actions">
          <button onClick={handleApply}>Apply</button>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </Modal>
  );
};

export default UploadFilesModal;