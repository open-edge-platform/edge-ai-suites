import React from 'react';
import { useTranslation } from 'react-i18next';
import ProjectLocationInput from './PathInput';

interface AudioPathInputProps {
  audioPath: string;
  onChange: (path: string) => void;
  onFolderClick: () => void;
}

const AudioPathInput: React.FC<AudioPathInputProps> = ({ audioPath, onChange, onFolderClick }) => {
  const { t } = useTranslation();
  
  return (
    <ProjectLocationInput
      value={audioPath}
      onChange={onChange}
      placeholder={t('settings.enterAudioPath')}
      prefix="audio/"
      showFolderIcon={true}
      onFolderClick={onFolderClick}
    />
  );
};

export default AudioPathInput;