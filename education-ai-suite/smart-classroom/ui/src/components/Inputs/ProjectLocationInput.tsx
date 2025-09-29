import React, { useRef, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import '../../assets/css/ProjectLocationInput.css';

interface ProjectLocationInputProps {
  projectLocation: string;
  onChange: (location: string) => void;
  placeholder?: string;
}

const ProjectLocationInput: React.FC<ProjectLocationInputProps> = ({
  projectLocation,
  onChange,
  placeholder,
}) => {
  const { t } = useTranslation();
  const effectivePlaceholder = placeholder ?? t('settings.projectLocationPlaceholder');
  const suffix = projectLocation.replace(/^storage\//, '');

  const prefixRef = useRef<HTMLSpanElement>(null);
  const [paddingLeft, setPaddingLeft] = useState(0);

 
  useEffect(() => {
    if (prefixRef.current) {
      setPaddingLeft(prefixRef.current.offsetWidth + 10); 
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange('storage/' + e.target.value);
  };

  return (
    <div className="project-location-input">
      <span ref={prefixRef} className="storage-prefix">storage/</span>
      <input
        type="text"
        value={suffix}
        onChange={handleChange}
        placeholder={effectivePlaceholder}
        className="project-location-field"
        style={{ paddingLeft: paddingLeft }}
      />
    </div>
  );
};

export default ProjectLocationInput;
