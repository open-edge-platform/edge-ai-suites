import React from 'react';
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
  return (
    <ProjectLocationInput
      value={boardCameraPath}
      onChange={onChange}
      placeholder="Enter board camera path"
      prefix="camera/board/"
      showFolderIcon={true}
      onFolderClick={onFolderClick}
    />
  );
};

export default BoardCameraPathInput;