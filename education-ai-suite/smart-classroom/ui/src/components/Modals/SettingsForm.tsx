import React, { useState, useEffect } from 'react';
import ProjectNameInput from '../Inputs/ProjectNameInput';
import MicrophoneSelect from '../Inputs/MicrophoneSelect';
import ProjectLocationInput from '../Inputs/ProjectLocationInput';
import '../../assets/css/SettingsForm.css';
import { saveSettings, getSettings, getAudioDevices } from '../../services/api';
import { useTranslation } from 'react-i18next';
import { useAppDispatch } from '../../redux/hooks';
import { setFrontCamera, setBackCamera, setBoardCamera } from '../../redux/slices/uiSlice';

interface SettingsFormProps {
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
}

const SettingsForm: React.FC<SettingsFormProps> = ({ onClose, projectName, setProjectName}) => {
  const [selectedMicrophone, setSelectedMicrophone] = useState('');
  const [projectLocation, setProjectLocation] = useState('storage/');
  const [frontCamera, setFrontCameraLocal] = useState('');
  const [backCamera, setBackCameraLocal] = useState('');
  const [boardCamera, setBoardCameraLocal] = useState('');
  const [nameError, setNameError] = useState<string | null>(null);
  const [availableDevices, setAvailableDevices] = useState<string[]>([]);
  const { t } = useTranslation();
  const dispatch = useAppDispatch();

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
          
          // Load camera settings - first try from API, then localStorage, then empty
          setFrontCameraLocal(settings.frontCamera || localStorage.getItem('frontCamera') || '');
          setBackCameraLocal(settings.backCamera || localStorage.getItem('backCamera') || '');
          setBoardCameraLocal(settings.boardCamera || localStorage.getItem('boardCamera') || '');
        
          if (settings.microphone && devices.includes(settings.microphone)) {
            setSelectedMicrophone(settings.microphone);
          } else if (devices.length > 0) {
            setSelectedMicrophone(devices[0]);
          } else {
            setSelectedMicrophone('');
          }
        } else {
          // Load camera settings from localStorage if no API settings
          setFrontCameraLocal(localStorage.getItem('frontCamera') || '');
          setBackCameraLocal(localStorage.getItem('backCamera') || '');
          setBoardCameraLocal(localStorage.getItem('boardCamera') || '');
          
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
        
        // Load camera settings from localStorage as fallback
        setFrontCameraLocal(localStorage.getItem('frontCamera') || '');
        setBackCameraLocal(localStorage.getItem('backCamera') || '');
        setBoardCameraLocal(localStorage.getItem('boardCamera') || '');
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
    
    console.log('Saving settings with cameras:', { frontCamera, backCamera, boardCamera }); 
    
    try {
      // Save all settings including cameras to backend
      await saveSettings({ 
        projectName, 
        projectLocation, 
        microphone: selectedMicrophone,
        frontCamera,
        backCamera,
        boardCamera
      });

      // Also save camera settings to localStorage as backup
      localStorage.setItem('frontCamera', frontCamera);
      localStorage.setItem('backCamera', backCamera);
      localStorage.setItem('boardCamera', boardCamera);

      // Update Redux state
      dispatch(setFrontCamera(frontCamera));
      dispatch(setBackCamera(backCamera));
      dispatch(setBoardCamera(boardCamera));

      onClose();
    } catch (error) {
      console.error('Failed to save settings:', error);
      
      // If backend save fails, at least save to localStorage and Redux
      localStorage.setItem('frontCamera', frontCamera);
      localStorage.setItem('backCamera', backCamera);
      localStorage.setItem('boardCamera', boardCamera);
      
      dispatch(setFrontCamera(frontCamera));
      dispatch(setBackCamera(backCamera));
      dispatch(setBoardCamera(boardCamera));
      
      onClose(); // Still close the modal
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

  const handleFrontCameraChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    console.log('Front camera changed to:', value);
    setFrontCameraLocal(value);
  };

  const handleBackCameraChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    console.log('Back camera changed to:', value);
    setBackCameraLocal(value);
  };

  const handleBoardCameraChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    console.log('Board camera changed to:', value);
    setBoardCameraLocal(value);
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

        {/* Camera Settings - Text Inputs */}
        <div>
          <label htmlFor="frontCamera">{t('settings.frontCamera')}</label>
          <input
            type="text"
            id="frontCamera"
            value={frontCamera}
            onChange={handleFrontCameraChange}
            placeholder={t('settings.frontCameraPlaceholder')}
            className="camera-input"
          />
        </div>

        <div>
          <label htmlFor="backCamera">{t('settings.backCamera')}</label>
          <input
            type="text"
            id="backCamera"
            value={backCamera}
            onChange={handleBackCameraChange}
            placeholder={t('settings.backCameraPlaceholder')}
            className="camera-input"
          />
        </div>

        <div>
          <label htmlFor="boardCamera">{t('settings.boardCamera')}</label>
          <input
            type="text"
            id="boardCamera"
            value={boardCamera}
            onChange={handleBoardCameraChange}
            placeholder={t('settings.boardCameraPlaceholder')}
            className="camera-input"
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