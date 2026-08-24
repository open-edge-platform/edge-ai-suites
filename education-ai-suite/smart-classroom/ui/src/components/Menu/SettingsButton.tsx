import React from 'react';
import Modal from '../Modals/Modal';
import SettingsForm from '../Modals/SettingsForm';
import type { FeatureGuard } from '../../utils/featureGuards';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
  featureGuard: FeatureGuard;
}

const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, projectName, setProjectName, featureGuard }) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} >
      <SettingsForm
        onClose={onClose}
        projectName={projectName}
        setProjectName={setProjectName}
        featureGuard={featureGuard}
      />
    </Modal>
  );
};

export default SettingsModal;