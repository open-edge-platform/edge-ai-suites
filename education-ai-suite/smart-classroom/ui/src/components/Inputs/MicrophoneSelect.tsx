import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getAudioDevices } from '../../services/api';

interface MicrophoneSelectProps {
  selectedMicrophone: string;
  onChange: (microphone: string) => void;
}

const MicrophoneSelect: React.FC<MicrophoneSelectProps> = ({
  selectedMicrophone,
  onChange
}) => {
  const { t } = useTranslation();
  const [devices, setDevices] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDevices = async () => {
      try {
        const audioDevices = await getAudioDevices();
        setDevices(audioDevices);
        if (!selectedMicrophone && audioDevices.length > 0) {
          const firstDevice = audioDevices[0].replace('audio=', '');
          onChange(firstDevice);
        }
      } catch (error) {
        console.error('❌ Failed to fetch audio devices:', error);
        setDevices([]);
      } finally {
        setLoading(false);
      }
    };

    fetchDevices();
  }, [t, onChange]);

  if (loading) {
    return (
      <select disabled>
        <option>{t('settings.loadingDevices')}</option>
      </select>
    );
  }

  if (devices.length === 0) {
    return (
      <select disabled>
        <option>{t('settings.noMicrophonesFound')}</option>
      </select>
    );
  }

  const getDisplayName = (device: string) => device.replace('audio=', '');
  const getStorageValue = (device: string) => device.replace('audio=', '');
  const currentValue = selectedMicrophone || '';

  return (
    <select
      value={currentValue}
      onChange={e => {
        const selectedValue = e.target.value;
        console.log('🎤 Microphone selected:', selectedValue);
        onChange(selectedValue);
      }}
      id="microphone"
    >
      <option value="">{t('settings.selectMicrophone')}</option>
      {devices.map((device, index) => {
        const storageValue = getStorageValue(device);
        const displayName = getDisplayName(device);
        
        return (
          <option key={index} value={storageValue}>
            {displayName}
          </option>
        );
      })}
    </select>
  );
};

export default MicrophoneSelect;