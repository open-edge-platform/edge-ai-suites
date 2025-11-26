import React, { useRef, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../../assets/css/ProjectLocationInput.css';

interface ProjectLocationInputProps {
  value: string;
  onChange: (location: string) => void;
  placeholder?: string;
  prefix?: string;
  showFolderIcon?: boolean; // New prop to show/hide folder icon
  onFolderClick?: () => void; // New callback for folder icon click
}

const ProjectLocationInput: React.FC<ProjectLocationInputProps> = ({
  value,
  onChange,
  placeholder,
  prefix = 'storage/',
  showFolderIcon = false,
  onFolderClick,
}) => {
  const { t } = useTranslation();
  const effectivePlaceholder = placeholder ?? t('settings.projectLocationPlaceholder');
  const suffix = value.replace(new RegExp(`^${prefix}`), ''); // Remove the prefix from the value

  const prefixRef = useRef<HTMLSpanElement>(null);
  const [paddingLeft, setPaddingLeft] = useState(0);

  useEffect(() => {
    if (prefixRef.current) {
      setPaddingLeft(prefixRef.current.offsetWidth + 10);
    }
  }, [prefix]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(prefix + e.target.value); // Add the prefix back to the value
  };

  return (
    <div className="project-location-input">
      <span ref={prefixRef} className="storage-prefix">{prefix}</span>
      <input
        type="text"
        value={suffix}
        onChange={handleChange}
        placeholder={effectivePlaceholder}
        className="project-location-field"
        style={{ paddingLeft: paddingLeft }}
      />
      {showFolderIcon && (
        <button
          type="button"
          className="folder-icon"
          onClick={onFolderClick}
          aria-label="Select Folder"
        >
          📂
        </button>
      )}
    </div>
  );
};

export default ProjectLocationInput;