import React from 'react';
import Modal from '../Modals/Modal';
import SettingsForm from '../Modals/SettingsForm';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
}

const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, projectName, setProjectName }) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} >
      <SettingsForm
        onClose={onClose}
        projectName={projectName}
        setProjectName={setProjectName}
      />
    </Modal>
  );
};

export default SettingsModal;
