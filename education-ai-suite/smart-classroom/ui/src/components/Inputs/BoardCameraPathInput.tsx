import React from 'react';
import { useTranslation } from 'react-i18next';
import ProjectLocationInput from './PathInput';

interface BoardCameraPathInputProps {
  boardCameraPath: string;
  onChange: (path: string) => void;
  onFolderClick: () => void;
  isabled?: boolean; // Add the disabled property
  placeholder?: string; 
}

const BoardCameraPathInput: React.FC<BoardCameraPathInputProps> = ({
  boardCameraPath,
  onChange,
  onFolderClick,
}) => {
  const { t } = useTranslation();
  
  return (
    <ProjectLocationInput
      value={boardCameraPath}
      onChange={onChange}
      placeholder={t('settings.enterBoardCameraPath')}
      prefix="camera/board/"
      showFolderIcon={true}
      onFolderClick={onFolderClick}
    />
  );
};

export default BoardCameraPathInput;