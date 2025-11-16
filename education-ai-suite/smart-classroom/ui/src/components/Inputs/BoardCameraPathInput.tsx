import React from 'react';
import ProjectLocationInput from './ProjectLocationInput';

interface BoardCameraPathInputProps {
  boardCameraPath: string;
  onChange: (path: string) => void;
  onFolderClick: () => void;
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