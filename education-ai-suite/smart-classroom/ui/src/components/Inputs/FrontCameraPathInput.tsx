import React from 'react';
import { useTranslation } from 'react-i18next';
import ProjectLocationInput from './PathInput';

interface FrontCameraPathInputProps {
  frontCameraPath: string;
  onChange: (path: string) => void;
  onFolderClick: () => void;
}

const FrontCameraPathInput: React.FC<FrontCameraPathInputProps> = ({
  frontCameraPath,
  onChange,
  onFolderClick,
}) => {
  const { t } = useTranslation();
  
  return (
    <ProjectLocationInput
      value={frontCameraPath}
      onChange={onChange}
      placeholder={t('settings.enterFrontCameraPath')}
      prefix="camera/front/"
      showFolderIcon={true}
      onFolderClick={onFolderClick}
    />
  );
};

export default FrontCameraPathInput;