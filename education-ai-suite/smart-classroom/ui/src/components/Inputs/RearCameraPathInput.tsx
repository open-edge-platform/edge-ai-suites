import React from 'react';
import { useTranslation } from 'react-i18next';
import ProjectLocationInput from './PathInput';

interface RearCameraPathInputProps {
  rearCameraPath: string;
  onChange: (path: string) => void;
  onFolderClick: () => void;
}

const RearCameraPathInput: React.FC<RearCameraPathInputProps> = ({
  rearCameraPath,
  onChange,
  onFolderClick,
}) => {
  const { t } = useTranslation();
  
  return (
    <ProjectLocationInput
      value={rearCameraPath}
      onChange={onChange}
      placeholder={t('settings.enterBackCameraPath')}
      prefix="camera/rear/"
      showFolderIcon={true}
      onFolderClick={onFolderClick}
    />
  );
};

export default RearCameraPathInput;