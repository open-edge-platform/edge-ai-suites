import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { gradingListDir } from '../../services/api';
import type { GradingFsEntry } from '../../services/api';

interface DirectoryPickerProps {
  initialPath?: string;
  onSelect: (path: string) => void;
  onClose: () => void;
}

const DirectoryPicker: React.FC<DirectoryPickerProps> = ({ initialPath, onSelect, onClose }) => {
  const { t } = useTranslation();

  const [path, setPath] = useState<string>('');
  const [parent, setParent] = useState<string | null>(null);
  const [entries, setEntries] = useState<GradingFsEntry[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  const navigate = async (target?: string) => {
    setLoading(true);
    setError('');
    try {
      const res = await gradingListDir(target);
      setPath(res.path);
      setParent(res.parent);
      setEntries(res.entries || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    navigate(initialPath || undefined);
  }, []);

  const atRoots = path === '';

  return (
    <div className="grading-picker-overlay" onClick={onClose}>
      <div className="grading-picker" onClick={(e) => e.stopPropagation()}>
        <div className="grading-picker-header">
          <span className="grading-picker-title">
            {t('grading.picker.title', 'Select a directory')}
          </span>
          <button className="grading-picker-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="grading-picker-path">
          <button
            className="grading-btn grading-btn-secondary grading-picker-up"
            disabled={loading || (atRoots && parent === null)}
            onClick={() => navigate(parent === null ? undefined : parent)}
          >
            {t('grading.picker.up', '↑ Up')}
          </button>
          <span className="grading-picker-current" title={path}>
            {path || t('grading.picker.roots', 'Drives')}
          </span>
        </div>

        {error && <div className="grading-error">{error}</div>}

        <div className="grading-picker-list">
          {loading && <div className="grading-picker-loading">{t('grading.picker.loading', 'Loading...')}</div>}
          {!loading && entries.length === 0 && (
            <div className="grading-picker-empty">{t('grading.picker.empty', 'Empty directory.')}</div>
          )}
          {!loading &&
            entries.map((entry) => (
              <div
                key={entry.path}
                className={`grading-picker-entry${entry.is_dir ? '' : ' is-file'}`}
                onClick={() => entry.is_dir && navigate(entry.path)}
              >
                <span className="grading-picker-icon">{entry.is_dir ? '📁' : '📄'}</span>
                <span className="grading-picker-name">{entry.name}</span>
              </div>
            ))}
        </div>

        <div className="grading-picker-footer">
          <button className="grading-btn grading-btn-secondary" onClick={onClose}>
            {t('grading.picker.cancel', 'Cancel')}
          </button>
          <button
            className="grading-btn grading-btn-primary"
            disabled={atRoots}
            onClick={() => onSelect(path)}
          >
            {t('grading.picker.select', 'Select this directory')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default DirectoryPicker;
