import React, { useState } from 'react';
import Modal from '../Modals/Modal';
import SettingsForm from '../Modals/SettingsForm';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
}

const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, projectName, setProjectName }) => {
  const [canClose, setCanClose] = useState<() => boolean>(() => () => true); // Default to always allow closing

  return (
    <Modal isOpen={isOpen} onClose={onClose} canClose={canClose}>
      <SettingsForm
        onClose={onClose}
        projectName={projectName}
        setProjectName={setProjectName}
        setCanClose={setCanClose} 
      />
    </Modal>
  );
};

export default SettingsModal;