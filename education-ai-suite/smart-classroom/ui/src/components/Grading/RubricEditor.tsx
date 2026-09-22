import React, { useEffect, useState } from 'react';
import { toErrorMessage } from './gradingUtils';
import { useTranslation } from 'react-i18next';
import { gradingGetRubricContent, gradingUpdateRubricContent } from '../../services/api';
import GradingModal from './GradingModal';

interface RubricEditorProps {
  filename: string;
  onClose: () => void;
}

const RubricEditor: React.FC<RubricEditorProps> = ({ filename, onClose }) => {
  const { t } = useTranslation();
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [saved, setSaved] = useState<boolean>(false);

  useEffect(() => {
    setLoading(true);
    setError('');
    gradingGetRubricContent(filename)
      .then((res) => setContent(res.content))
      .catch((e) => setError(toErrorMessage(e)))
      .finally(() => setLoading(false));
  }, [filename]);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      await gradingUpdateRubricContent(filename, content);
      setSaved(true);
    } catch (e) {
      setError(toErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <GradingModal
      title={`${t('grading.editor.title', 'Edit Rubric')} — ${filename}`}
      onClose={onClose}
      className="grading-editor"
    >
      <div className="grading-editor-body">
          {loading ? (
            <div className="grading-picker-loading">{t('grading.editor.loading', 'Loading…')}</div>
          ) : (
            <textarea
              className="grading-editor-textarea"
              value={content}
              onChange={(e) => { setContent(e.target.value); setSaved(false); }}
              spellCheck={false}
            />
          )}
        </div>

        {error && <div className="grading-error" style={{ padding: '0 18px' }}>{error}</div>}

        <div className="grading-picker-footer">
          {saved && (
            <span className="grading-editor-saved">{t('grading.editor.saved', 'Saved.')}</span>
          )}
          <button className="grading-btn grading-btn-secondary" onClick={onClose}>
            {t('grading.editor.close', 'Close')}
          </button>
          <button
            className="grading-btn grading-btn-primary"
            onClick={handleSave}
            disabled={saving || loading}
          >
            {saving ? t('grading.editor.saving', 'Saving…') : t('grading.editor.save', 'Save')}
          </button>
        </div>
    </GradingModal>
  );
};

export default RubricEditor;
