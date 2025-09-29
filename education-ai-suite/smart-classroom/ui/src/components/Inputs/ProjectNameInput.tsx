import React from 'react';
import { useTranslation } from 'react-i18next';

interface ProjectNameInputProps {
  projectName: string;
  onChange: (name: string) => void; 
  placeholder?: string;
  maxLength?: number;
  autoFocus?: boolean;
}

const ProjectNameInput: React.FC<ProjectNameInputProps> = ({
  projectName,
  onChange,
  placeholder,
  maxLength = 32,
  autoFocus = false,
}) => {
  const { t } = useTranslation();
  const effectivePlaceholder = placeholder ?? t('settings.projectNamePlaceholder');
  return (
    <input
      type="text"
      value={projectName}
      onChange={(e) => onChange(e.target.value)} 
      id="projectName"
      placeholder={effectivePlaceholder}
      maxLength={maxLength}
      autoFocus={autoFocus}
      style={{ background: "#f8f8f8" }}
    />
  );
};

export default ProjectNameInput;