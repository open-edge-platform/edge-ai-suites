import React from 'react';
import ProjectLocationInput from './PathInput';

interface AudioPathInputProps {
  audioPath: string;
  onChange: (path: string) => void;
  onFolderClick: () => void;
}

const AudioPathInput: React.FC<AudioPathInputProps> = ({ audioPath, onChange, onFolderClick }) => {
  return (
    <ProjectLocationInput
      value={audioPath}
      onChange={onChange}
      placeholder="Enter audio path"
      prefix="audio/"
      showFolderIcon={true}
      onFolderClick={onFolderClick}
    />
  );
};

export default AudioPathInput;