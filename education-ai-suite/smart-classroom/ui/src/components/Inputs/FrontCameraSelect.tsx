import React from 'react';
import { useTranslation } from 'react-i18next';

interface FrontCameraSelectProps {
  selectedFrontCamera: string;
  onChange: (camera: string) => void;
  isabled?: boolean; // Add the disabled property
  placeholder?: string; 
}

const FrontCameraSelect: React.FC<FrontCameraSelectProps> = ({
  selectedFrontCamera,
  onChange
}) => {
  const { t } = useTranslation();
  return (
    <select
      value={selectedFrontCamera}
      onChange={(e) => onChange(e.target.value)}
      id="frontCamera"
    >
      <option value="Default Front Camera">{t('settings.defaultFrontCamera')}</option>
      <option value="Front Camera 1">{t('settings.frontCamera1')}</option>
      <option value="Front Camera 2">{t('settings.frontCamera2')}</option>
    </select>
  );
};

export default FrontCameraSelect;