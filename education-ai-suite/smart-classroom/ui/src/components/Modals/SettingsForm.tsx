import React, { useState, useEffect } from 'react';
import ProjectNameInput from '../Inputs/ProjectNameInput';
import MicrophoneSelect from '../Inputs/MicrophoneSelect';
import ProjectLocationInput from '../Inputs/ProjectLocationInput';
import '../../assets/css/SettingsForm.css';
import { saveSettings, getSettings } from '../../services/api';
import { useTranslation } from 'react-i18next';

interface SettingsFormProps {
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
  setCanClose: (canClose: () => boolean) => void; // Add setCanClose to props
}

const SettingsForm: React.FC<SettingsFormProps> = ({ onClose, projectName, setProjectName, setCanClose }) => {
  const [selectedMicrophone, setSelectedMicrophone] = useState('');
  const [projectLocation, setProjectLocation] = useState('storage/');
  const [nameError, setNameError] = useState<string | null>(null);
  const { t } = useTranslation();

  // Fetch settings on mount and set defaults
  useEffect(() => {
    getSettings()
      .then(s => {
        if (!s) return;
        setProjectLocation(s.projectLocation || 'storage/');
        setSelectedMicrophone(s.microphone || '');
        if (s.projectName) setProjectName(s.projectName); // default project name from API
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

  // Pass validation logic to Modal
  useEffect(() => {
    setCanClose(validateProjectName); // Pass validation logic to Modal
  }, [projectName, setCanClose]);

  const handleSave = async () => {
    if (!validateProjectName()) {
      return;
    }
    try {
      await saveSettings({ projectName, projectLocation, microphone: selectedMicrophone });
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
            projectLocation={projectLocation}
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
      </div>
      <div className="button-container">
        <button onClick={handleSave} className="submit-button">{t('settings.ok')}</button>
      </div>
    </div>
  );
};

export default SettingsForm;