import React from 'react';
import { useTranslation } from 'react-i18next';

interface BoardCameraSelectProps {
  selectedBoardCamera: string;
  onChange: (camera: string) => void;
}

const BoardCameraSelect: React.FC<BoardCameraSelectProps> = ({
  selectedBoardCamera,
  onChange
}) => {
  const { t } = useTranslation();
  return (
    <select
      value={selectedBoardCamera}
      onChange={(e) => onChange(e.target.value)}
      id="boardCamera"
    >
      <option value="Default Board Camera">{t('settings.defaultBoardCamera')}</option>
      <option value="Board Camera 1">{t('settings.boardCamera1')}</option>
      <option value="Board Camera 2">{t('settings.boardCamera2')}</option>
    </select>
  );
};

export default BoardCameraSelect;