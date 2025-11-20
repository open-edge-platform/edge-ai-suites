import React from 'react';
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
  return (
    <ProjectLocationInput
      value={rearCameraPath}
      onChange={onChange}
      placeholder="Enter rear camera path"
      prefix="camera/rear/"
      showFolderIcon={true}
      onFolderClick={onFolderClick}
    />
  );
};

export default RearCameraPathInput;