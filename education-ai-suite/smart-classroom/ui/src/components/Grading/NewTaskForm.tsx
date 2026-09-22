import React, { useEffect, useRef, useState } from 'react';
import { toErrorMessage } from './gradingUtils';
import { useTranslation } from 'react-i18next';
import {
  gradingListRubrics,
  gradingUploadRubric,
  gradingCreateTask,
} from '../../services/api';
import type { GradingRubricInfo } from '../../services/api';
import DirectoryPicker from './DirectoryPicker';
import RubricEditor from './RubricEditor';

interface NewTaskFormProps {
  onTaskCreated: () => void;
}

const NewTaskForm: React.FC<NewTaskFormProps> = ({ onTaskCreated }) => {
  const { t } = useTranslation();

  const [rubrics, setRubrics] = useState<GradingRubricInfo[]>([]);
  const [rubricPath, setRubricPath] = useState<string>('');
  const [paperPath, setPaperPath] = useState<string>('');

  const [loadingRubrics, setLoadingRubrics] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [pickerOpen, setPickerOpen] = useState<boolean>(false);
  const [editorOpen, setEditorOpen] = useState<boolean>(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const isElectron = !!window.electronAPI?.isElectron;

  const loadRubrics = async (selectPath?: string) => {
    setLoadingRubrics(true);
    setError('');
    try {
      const res = await gradingListRubrics();
      const list = res.rubrics || [];
      setRubrics(list);
      if (selectPath) {
        setRubricPath(selectPath);
      } else if (!rubricPath && list.length > 0) {
        setRubricPath(list[0].rubric_path);
      }
    } catch (e) {
      setError(toErrorMessage(e));
    } finally {
      setLoadingRubrics(false);
    }
  };

  useEffect(() => {
    loadRubrics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (fileInputRef.current) fileInputRef.current.value = '';
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const res = await gradingUploadRubric(file);
      await loadRubrics(res.rubric_path);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  // In Electron, use the OS-native folder chooser: the app and the Python
  // backends run on the same machine, so a locally picked path is also readable
  // by the server. On the web, fall back to the in-app picker that browses the
  // server's filesystem over the API.
  const handleBrowse = async () => {
    if (!window.electronAPI?.pickDirectory) {
      setPickerOpen(true);
      return;
    }
    try {
      const picked = await window.electronAPI.pickDirectory(paperPath || undefined);
      if (picked) setPaperPath(picked);
    } catch (e) {
      setError(toErrorMessage(e));
    }
  };

  const handleStart = async () => {
    if (!paperPath.trim()) {
      setError(t('grading.form.needPaperPath', 'Please enter the target directory or file path.'));
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await gradingCreateTask({
        paper_path: paperPath.trim(),
        rubric_path: rubricPath || undefined,
      });
      onTaskCreated();
      setPaperPath('');
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grading-newtask">
      <h3 className="grading-section-title">{t('grading.form.title', 'New grading task')}</h3>

      <div className="grading-form-row">
        <label className="grading-form-label">{t('grading.form.rubric', 'Rubric')}</label>
        <div className="grading-form-control">
          <select
            className="grading-select"
            value={rubricPath}
            onChange={(e) => setRubricPath(e.target.value)}
            disabled={loadingRubrics || rubrics.length === 0}
          >
            {rubrics.length === 0 && (
              <option value="">{t('grading.form.noRubric', 'No rubric available')}</option>
            )}
            {rubrics.map((r) => (
              <option key={r.rubric_path} value={r.rubric_path}>
                {r.filename}
              </option>
            ))}
          </select>
        </div>
        <div className="grading-form-btns">
          <button
            className="grading-btn grading-btn-secondary"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? t('grading.form.uploading', 'Uploading...') : t('grading.form.upload', 'Upload')}
          </button>
          <button
            className="grading-btn grading-btn-secondary"
            onClick={() => setEditorOpen(true)}
            disabled={!rubricPath}
            title={rubricPath ? undefined : t('grading.form.editDisabledHint', 'Select a rubric first')}
          >
            {t('grading.form.edit', 'Edit')}
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: 'none' }}
          onChange={handleUpload}
        />
      </div>

      <div className="grading-form-row">
        <label className="grading-form-label">{t('grading.form.paperPath', 'Target directory')}</label>
        <div className="grading-form-control">
          <input
            className="grading-input"
            type="text"
            value={paperPath}
            onChange={(e) => setPaperPath(e.target.value)}
            placeholder={t('grading.form.paperPathPlaceholder', '/abs/path/to/papers')}
          />
        </div>
        <div className="grading-form-btns">
          <button
            className="grading-btn grading-btn-secondary"
            onClick={handleBrowse}
          >
            {t('grading.form.browse', 'Browse')}
          </button>
          <button
            className="grading-btn grading-btn-start"
            onClick={handleStart}
            disabled={submitting || !rubricPath || !paperPath.trim()}
          >
            {submitting ? t('grading.form.starting', 'Starting...') : t('grading.form.start', 'Start')}
          </button>
        </div>
      </div>
      {!isElectron && (
        <div className="grading-form-hint">
          {t('grading.form.pathHint', 'A path visible to the server, not a browser upload.')}
        </div>
      )}

      {error && <div className="grading-error">{error}</div>}

      {pickerOpen && (
        <DirectoryPicker
          initialPath={paperPath || undefined}
          onSelect={(p) => {
            setPaperPath(p);
            setPickerOpen(false);
          }}
          onClose={() => setPickerOpen(false)}
        />
      )}

      {editorOpen && rubricPath && (
        <RubricEditor
          filename={rubrics.find((r) => r.rubric_path === rubricPath)?.filename ?? rubricPath.split(/[\\/]/).pop() ?? rubricPath}
          onClose={() => setEditorOpen(false)}
        />
      )}
    </div>
  );
};

export default NewTaskForm;
