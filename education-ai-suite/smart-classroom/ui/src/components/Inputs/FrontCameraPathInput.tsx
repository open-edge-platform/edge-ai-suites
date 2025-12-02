import React from 'react';
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
  return (
    <ProjectLocationInput
      value={frontCameraPath}
      onChange={onChange}
      placeholder="Enter front camera path"
      prefix="camera/front/"
      showFolderIcon={true}
      onFolderClick={onFolderClick}
    />
  );
};

export default FrontCameraPathInput;