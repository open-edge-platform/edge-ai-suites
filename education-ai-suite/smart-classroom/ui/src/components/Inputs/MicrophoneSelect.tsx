import React from 'react';
import { useTranslation } from 'react-i18next';

interface MicrophoneSelectProps {
  selectedMicrophone: string;
  onChange: (microphone: string) => void;
}

const MicrophoneSelect: React.FC<MicrophoneSelectProps> = ({
  selectedMicrophone,
  onChange
}) => {
  const { t } = useTranslation();
  const defaultVal = selectedMicrophone || t('settings.ipMicrophone');
  return (
    <select
      value={defaultVal}
      onChange={e => onChange(e.target.value)}
      id="microphone"
      disabled
    >
      <option value={t('settings.ipMicrophone')!}>{t('settings.ipMicrophone')}</option>
    </select>
  );
};

export default MicrophoneSelect;