import React, { useState, useEffect } from 'react';
import ProjectNameInput from '../Inputs/ProjectNameInput';
import MicrophoneSelect from '../Inputs/MicrophoneSelect';
import ProjectLocationInput from '../Inputs/ProjectLocationInput';
import '../../assets/css/SettingsForm.css';
import { saveSettings, getSettings, getAudioDevices } from '../../services/api';
import { useTranslation } from 'react-i18next';

interface SettingsFormProps {
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
}

const SettingsForm: React.FC<SettingsFormProps> = ({ onClose, projectName, setProjectName}) => {
  const [selectedMicrophone, setSelectedMicrophone] = useState('');
  const [projectLocation, setProjectLocation] = useState('storage/');
  const [nameError, setNameError] = useState<string | null>(null);
  const [availableDevices, setAvailableDevices] = useState<string[]>([]);
  const { t } = useTranslation();

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const [settings, devices] = await Promise.all([
          getSettings(),
          getAudioDevices()
        ]);
        setAvailableDevices(devices);
        
        if (settings) {
          setProjectLocation(settings.projectLocation || 'storage/');
          if (settings.projectName) setProjectName(settings.projectName);
        
          if (settings.microphone && devices.includes(settings.microphone)) {
            setSelectedMicrophone(settings.microphone);
          } else if (devices.length > 0) {
            setSelectedMicrophone(devices[0]);
          } else {
            setSelectedMicrophone('');
          }
        } else {
          if (devices.length > 0) {
            console.log('No saved settings, using first device:', devices[0]);
            setSelectedMicrophone(devices[0]);
          } else {
            console.log('No saved settings and no devices available');
            setSelectedMicrophone('');
          }
        }
      } catch (error) {
        console.error('Failed to load settings or devices:', error);
        setAvailableDevices([]);
        setSelectedMicrophone('');
      }
    };

    loadSettings();
  }, [setProjectName, t]);

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
    
    console.log('Saving settings with microphone:', selectedMicrophone); 
    
    try {
      await saveSettings({ 
        projectName, 
        projectLocation, 
        microphone: selectedMicrophone 
      });
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

  const handleMicrophoneChange = (microphone: string) => {
    console.log('Microphone changed to:', microphone); 
    setSelectedMicrophone(microphone);
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
        <div>
          <label htmlFor="microphone">{t('settings.microphone')}</label>
          {availableDevices.length > 0 ? (
            <MicrophoneSelect
              selectedMicrophone={selectedMicrophone}
              onChange={handleMicrophoneChange}
            />
          ) : (
            <div className="no-devices-message">
              No devices available
            </div>
          )}
          <div className="debug-info">
            Selected: {selectedMicrophone || 'None'} | Available: {availableDevices.length}
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