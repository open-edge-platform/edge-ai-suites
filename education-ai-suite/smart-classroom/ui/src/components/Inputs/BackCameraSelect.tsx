import React from 'react';
import { useTranslation } from 'react-i18next';

interface BackCameraSelectProps {
  selectedBackCamera: string;
  onChange: (camera: string) => void;
  disabled?: boolean; // Add the disabled property
  placeholder?: string; 
}

const BackCameraSelect: React.FC<BackCameraSelectProps> = ({
  selectedBackCamera,
  onChange,
  disabled = false,
  placeholder = "Select",
}) => {
  const { t } = useTranslation();
  return (
    <select
      value={selectedBackCamera}
      onChange={(e) => onChange(e.target.value)}
      id="backCamera"
      disabled={disabled} // Use the disabled property
    > 
    <option value="" disabled>
      {placeholder}
    </option>
      <option value="Default Back Camera">{t('settings.defaultBackCamera')}</option>
      <option value="Back Camera 1">{t('settings.backCamera1')}</option>
      <option value="Back Camera 2">{t('settings.backCamera2')}</option>
    </select>
  );
};

export default BackCameraSelect;