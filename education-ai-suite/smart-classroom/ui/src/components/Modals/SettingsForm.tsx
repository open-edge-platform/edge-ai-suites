import React, { useState, useEffect } from 'react';
import ProjectNameInput from '../Inputs/ProjectNameInput';
import MicrophoneSelect from '../Inputs/MicrophoneSelect';
import ProjectLocationInput from '../Inputs/ProjectLocationInput';
import FrontCameraSelect from '../Inputs/FrontCameraSelect';
import BackCameraSelect from '../Inputs/BackCameraSelect';
import BoardCameraSelect from '../Inputs/BoardCameraSelect';
import '../../assets/css/SettingsForm.css';
import { saveSettings, getSettings } from '../../services/api';
import { useTranslation } from 'react-i18next';

interface SettingsFormProps {
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
}

const SettingsForm: React.FC<SettingsFormProps> = ({ onClose, projectName, setProjectName}) => {
  const [selectedMicrophone, setSelectedMicrophone] = useState('');
  const [projectLocation, setProjectLocation] = useState('storage/');
  const [selectedFrontCamera, setSelectedFrontCamera] = useState('Default Front Camera');
  const [selectedBackCamera, setSelectedBackCamera] = useState('Default Back Camera');
  const [selectedBoardCamera, setSelectedBoardCamera] = useState('Default Board Camera');
  const [nameError, setNameError] = useState<string | null>(null);
  const { t } = useTranslation();

  // Fetch settings on mount and set defaults
  useEffect(() => {
    getSettings()
      .then(s => {
        if (!s) return;
        setProjectLocation(s.projectLocation || 'storage/');
        setSelectedMicrophone(s.microphone || '');
        setSelectedFrontCamera(s.frontCamera || 'Default Front Camera');
        setSelectedBackCamera(s.backCamera || 'Default Back Camera');
        setSelectedBoardCamera(s.boardCamera || 'Default Board Camera');
        if (s.projectName) setProjectName(s.projectName); 
      })
      .catch(() => {});
  }, [setProjectName]);

  // Validate project name
  const validateProjectName = () => {
    if (!projectName.trim()) {
      setNameError(t('errors.projectNameRequired'));
      return false;
    }
    return true;
  };

  const handleSave = async () => {
    if (!validateProjectName()) {
      return;
    }
    try {
      await saveSettings({ projectName, projectLocation, microphone: selectedMicrophone, frontCamera: selectedFrontCamera,
        backCamera: selectedBackCamera,
        boardCamera: selectedBoardCamera });
      onClose();
    } catch (error) {
      console.error('Failed to save settings:', error);
    }
  };

  const handleNameChange = (name: string) => {
    setProjectName(name);
    if (nameError) setNameError(null);
  };
  const handleLocationChange = (location: string) => {
    setProjectLocation(location);
  };
  return (
    <div className="settings-form">
      <h2>{t('settings.title')}</h2>
      <hr className="settings-title-line" />
      <div className="settings-body">
        <div>
          <label htmlFor="projectName">{t('settings.projectName')}</label>
          <ProjectNameInput projectName={projectName} onChange={handleNameChange} />
          {nameError && (
            <div style={{ color: '#c00', fontSize: 12, marginTop: 4 }}>
              {nameError}
            </div>
          )}
        </div>
        <div>
          <label htmlFor="projectLocation">{t('settings.projectLocation')}</label>
          <ProjectLocationInput
            value={projectLocation}
            onChange={handleLocationChange}
            placeholder=""
          />
        </div>
        <div>
          <label htmlFor="microphone">{t('settings.microphone')}</label>
          <MicrophoneSelect
            selectedMicrophone={selectedMicrophone}
            onChange={setSelectedMicrophone}
          />
        </div>
        <div className="camera-row">
          <div>
            <label htmlFor="frontCamera">{t('settings.frontCamera')}</label>
            <FrontCameraSelect
              selectedFrontCamera={selectedFrontCamera}
              onChange={setSelectedFrontCamera}
            />
          </div>
          <div>
            <label htmlFor="backCamera">{t('settings.backCamera')}</label>
            <BackCameraSelect
              selectedBackCamera={selectedBackCamera}
              onChange={setSelectedBackCamera}
            />
          </div>
          <div>
            <label htmlFor="boardCamera">{t('settings.boardCamera')}</label>
            <BoardCameraSelect
              selectedBoardCamera={selectedBoardCamera}
              onChange={setSelectedBoardCamera}
            />
          </div>
        </div>
      </div>
      <div className="button-container">
        <button onClick={handleSave} className="submit-button">{t('settings.ok')}</button>
      </div>
    </div>
  );
};

export default SettingsForm;