import React, { useState, useEffect } from 'react';
import ProjectNameInput from '../Inputs/ProjectNameInput';
import ProjectLocationInput from '../Inputs/ProjectLocationInput';
import '../../assets/css/SettingsForm.css';
import { saveSettings, getSettings } from '../../services/api';
import { useTranslation } from 'react-i18next';

interface SettingsFormProps {
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
}

// Where the project lives.
const SettingsForm: React.FC<SettingsFormProps> = ({ onClose, projectName, setProjectName }) => {
  const [projectLocation, setProjectLocation] = useState('storage/');
  // Not editable here, but carried so saving a name cannot blank the device the
  // backend records with — POST /project writes whatever it is given.
  const [microphone, setMicrophone] = useState('');
  const [nameError, setNameError] = useState<string | null>(null);
  const { t } = useTranslation();

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const settings = await getSettings();
        if (!settings) return;
        setProjectLocation(settings.projectLocation || 'storage/');
        setMicrophone(settings.microphone || '');
        if (settings.projectName) setProjectName(settings.projectName);
      } catch (error) {
        console.error('Failed to load settings:', error);
      }
    };

    loadSettings();
  }, [setProjectName]);

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
      await saveSettings({ projectName, projectLocation, microphone });
    } catch (error) {
      console.error('Failed to save settings:', error);
    }

    onClose();
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
            <div className="error-message">
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
      </div>
      <div className="button-container">
        <button onClick={handleSave} className="submit-button">{t('settings.ok')}</button>
      </div>
    </div>
  );
};

export default SettingsForm;
