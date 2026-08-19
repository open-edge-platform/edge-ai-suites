import React, { useState, useEffect } from 'react';
import ProjectNameInput from '../Inputs/ProjectNameInput';
import MicrophoneSelect from '../Inputs/MicrophoneSelect';
import ProjectLocationInput from '../Inputs/ProjectLocationInput';
import '../../assets/css/SettingsForm.css';
import { saveSettings, getSettings, getAudioDevices } from '../../services/api';
import { useTranslation } from 'react-i18next';
import { useAppDispatch } from '../../redux/hooks';
import { setFrontCamera, setBackCamera, setBoardCamera } from '../../redux/slices/uiSlice';
import type { FeatureGuard } from '../../utils/featureGuards';

interface SettingsFormProps {
  onClose: () => void;
  projectName: string;
  setProjectName: (name: string) => void;
  featureGuard: FeatureGuard;
}

const SettingsForm: React.FC<SettingsFormProps> = ({ onClose, projectName, setProjectName, featureGuard }) => {
  const [selectedMicrophone, setSelectedMicrophone] = useState('');
  const [projectLocation, setProjectLocation] = useState('storage/');
  const [frontCamera, setFrontCameraLocal] = useState('');
  const [backCamera, setBackCameraLocal] = useState('');
  const [boardCamera, setBoardCameraLocal] = useState('');
  const [nameError, setNameError] = useState<string | null>(null);
  const [availableDevices, setAvailableDevices] = useState<string[]>([]);
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  
  // Check feature flags
  const hasAudioFeatures = featureGuard.hasFeature('asr') || 
                           featureGuard.hasFeature('summary') || 
                           featureGuard.hasFeature('mindmap') || 
                           featureGuard.hasFeature('topic_segmentation') || 
                           featureGuard.hasFeature('report');
  const hasVideoAnalyticsFeature = featureGuard.hasFeature('video_analytics');

  useEffect(() => {
    const loadSettings = async () => {
      try {
        // Only fetch audio devices if audio features are enabled
        const settingsPromises: [Promise<any>, Promise<string[]>?] = [getSettings()];
        if (hasAudioFeatures) {
          settingsPromises.push(getAudioDevices());
        }
        
        const results = await Promise.all(settingsPromises);
        const settings = results[0];
        const devices = hasAudioFeatures ? (results[1] || []) : [];
        
        setAvailableDevices(devices);
        
        if (settings) {
          setProjectLocation(settings.projectLocation || 'storage/');
          if (settings.projectName) setProjectName(settings.projectName);
          setFrontCameraLocal(settings.frontCamera || '');
          setBackCameraLocal(settings.backCamera || '');
          setBoardCameraLocal(settings.boardCamera || '');
        
          if (hasAudioFeatures) {
            if (settings.microphone && devices.includes(settings.microphone)) {
              setSelectedMicrophone(settings.microphone);
            } else if (devices.length > 0) {
              setSelectedMicrophone(devices[0]);
            } else {
              setSelectedMicrophone('');
            }
          }
        } else {
          setFrontCameraLocal('');
          setBackCameraLocal('');
          setBoardCameraLocal('');
          
          if (hasAudioFeatures) {
            if (devices.length > 0) {
              console.log('No saved settings, using first device:', devices[0]);
              setSelectedMicrophone(devices[0]);
            } else {
              console.log('No saved settings and no devices available');
              setSelectedMicrophone('');
            }
          }
        }
      } catch (error) {
        console.error('Failed to load settings or devices:', error);
        setAvailableDevices([]);
        setSelectedMicrophone('');
        setFrontCameraLocal('');
        setBackCameraLocal('');
        setBoardCameraLocal('');
      }
    };

    loadSettings();
  }, [setProjectName, t, hasAudioFeatures]);

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
      await saveSettings({ 
        projectName, 
        projectLocation, 
        microphone: selectedMicrophone,
        frontCamera,
        backCamera,
        boardCamera
      });
      dispatch(setFrontCamera(frontCamera));
      dispatch(setBackCamera(backCamera));
      dispatch(setBoardCamera(boardCamera));

      console.log('✅ Settings saved and Redux updated:', {
        frontCamera,
        backCamera,
        boardCamera
      });

      onClose();
    } catch (error) {
      console.error('Failed to save settings:', error);

      dispatch(setFrontCamera(frontCamera));
      dispatch(setBackCamera(backCamera));
      dispatch(setBoardCamera(boardCamera));
      
      onClose(); 
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
        
        {/* Microphone settings - only show if audio features are enabled */}
        {hasAudioFeatures ? (
          <div>
            <label htmlFor="microphone">{t('settings.microphone')}</label>
            {availableDevices.length > 0 ? (
              <MicrophoneSelect
                selectedMicrophone={selectedMicrophone}
                onChange={handleMicrophoneChange}
              />
            ) : (
              <div className="no-devices-message">
                {t('settings.noDevicesAvailable')}
              </div>
            )}
            <div className="debug-info">
              {t('settings.deviceSelectionInfo', {
                selected: selectedMicrophone || t('settings.noneSelected'),
                count: availableDevices.length,
              })}
            </div>
          </div>
        ) : (
          <div className="modal-info-message" style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#f0f0f0', borderRadius: '4px', color: '#666' }}>
            {t('settings.audioFeaturesDisabled')}
          </div>
        )}
        
        {/* Camera settings - only show if video_analytics is enabled */}
        {hasVideoAnalyticsFeature ? (
          <>
            <div>
              <label htmlFor="frontCamera">{t('settings.frontCamera')}</label>
              <input
                type="text"
                id="frontCamera"
                value={frontCamera}
                onChange={handleFrontCameraChange}
                placeholder="rtsp://127.0.0.1:9554/front"
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
                placeholder="rtsp://127.0.0.1:9554/back"
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
                placeholder="rtsp://127.0.0.1:9554/content"
                className="camera-input"
              />
            </div>
          </>
        ) : (
          <div className="modal-info-message" style={{ marginBottom: '1rem', padding: '0.75rem', backgroundColor: '#f0f0f0', borderRadius: '4px', color: '#666' }}>
            {t('settings.videoAnalyticsDisabled')}
          </div>
        )}
      </div>
      <div className="button-container">
        <button onClick={handleSave} className="submit-button">{t('settings.ok')}</button>
      </div>
    </div>
  );
};

export default SettingsForm;