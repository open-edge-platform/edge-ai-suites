import React from 'react';
import Modal from './Modal';
import SettingsForm from './SettingsForm';

interface WelcomeModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
}

const WelcomeModal: React.FC<WelcomeModalProps> = ({ isOpen, onClose, projectName, setProjectName }) => {
  return (
    <Modal isOpen={isOpen} onClose={onClose} >
      <SettingsForm 
        onClose={onClose} 
        projectName={projectName} 
        setProjectName={setProjectName} 
        setCanClose={() => true} // Provide a default setCanClose function
      />
    </Modal>
  );
};

export default WelcomeModal;