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
  const { t } = useTranslation();

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const [settings, devices] = await Promise.all([
          getSettings(),
          getAudioDevices()
        ]);
        
        // Create full device list with IP microphone first
        const ipMicrophone = t('settings.ipMicrophone');
        const allDevices = [ipMicrophone, ...devices];
        
        console.log('Available devices:', allDevices); // Debug log
        console.log('Saved microphone from settings:', settings?.microphone); // Debug log
        
        if (settings) {
          setProjectLocation(settings.projectLocation || 'storage/');
          if (settings.projectName) setProjectName(settings.projectName);
          
          // Set microphone: use saved value if it exists in available devices, otherwise use first device
          if (settings.microphone && allDevices.includes(settings.microphone)) {
            console.log('Using saved microphone:', settings.microphone);
            setSelectedMicrophone(settings.microphone);
          } else {
            console.log('Using default microphone:', allDevices[0]);
            setSelectedMicrophone(allDevices[0]);
          }
        } else {
          // No saved settings, use first available device
          console.log('No saved settings, using first device:', allDevices[0]);
          setSelectedMicrophone(allDevices[0]);
        }
      } catch (error) {
        console.error('Failed to load settings or devices:', error);
        // Fallback to IP microphone
        const fallback = t('settings.ipMicrophone');
        console.log('Error fallback, using:', fallback);
        setSelectedMicrophone(fallback);
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
    
    console.log('Saving settings with microphone:', selectedMicrophone); // Debug log
    
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
    console.log('Microphone changed to:', microphone); // Debug log
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
            onChange={handleMicrophoneChange}
          />
          {/* Debug display */}
          <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
            Selected: {selectedMicrophone || 'None'}
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