import React from 'react';
import { useTranslation } from 'react-i18next';

interface BackCameraSelectProps {
  selectedBackCamera: string;
  onChange: (camera: string) => void;
}

const BackCameraSelect: React.FC<BackCameraSelectProps> = ({
  selectedBackCamera,
  onChange
}) => {
  const { t } = useTranslation();
  return (
    <select
      value={selectedBackCamera}
      onChange={(e) => onChange(e.target.value)}
      id="backCamera"
    >
      <option value="Default Back Camera">{t('settings.defaultBackCamera')}</option>
      <option value="Back Camera 1">{t('settings.backCamera1')}</option>
      <option value="Back Camera 2">{t('settings.backCamera2')}</option>
    </select>
  );
};

export default BackCameraSelect;