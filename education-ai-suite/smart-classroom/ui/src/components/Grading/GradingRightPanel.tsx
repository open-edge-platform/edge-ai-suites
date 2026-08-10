import React, { useEffect, useState } from 'react';
import { toErrorMessage } from './gradingUtils';
import { useTranslation } from 'react-i18next';
import Accordion from '../common/Accordion';
import { getPlatformInfo, gradingGetConfig, gradingUpdateConfig } from '../../services/api';
import type { GradingConfig } from '../../services/api';
import '../../assets/css/RightPanel.css';

const dash = '-';

const GradingRightPanel: React.FC = () => {
  const { t } = useTranslation();
  const [platformData, setPlatformData] = useState<any>(null);
  const [config, setConfig] = useState<GradingConfig | null>(null);

  const numKeys = ['dpi', 'page_columns', 'column_split_ratio', 'contrast_factor', 'max_tokens', 'vlm_temperature', 'max_image_pixels',
    'poll_interval', 'stable_checks', 'idle_timeout', 'min_score', 'expand_margin', 'iou_threshold'] as const;
  const boolKeys = ['force_split', 'contrast_enhance', 'sort_boxes', 'merge_overlapping'] as const;
  type NumKey = typeof numKeys[number];
  type BoolKey = typeof boolKeys[number];

  const [numInputs, setNumInputs] = useState<Record<NumKey, string>>(() =>
    Object.fromEntries(numKeys.map((k) => [k, ''])) as Record<NumKey, string>);
  const [boolInputs, setBoolInputs] = useState<Record<BoolKey, boolean>>(() =>
    Object.fromEntries(boolKeys.map((k) => [k, false])) as Record<BoolKey, boolean>);
  const [splitPagesInput, setSplitPagesInput] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string>('');

  const applyConfig = (cfg: GradingConfig) => {
    setConfig(cfg);
    setNumInputs(Object.fromEntries(numKeys.map((k) =>
      [k, cfg[k] != null ? String(cfg[k]) : ''])) as Record<NumKey, string>);
    setBoolInputs(Object.fromEntries(boolKeys.map((k) =>
      [k, Boolean(cfg[k])])) as Record<BoolKey, boolean>);
    setSplitPagesInput(Array.isArray(cfg.force_split_pairs) ? cfg.force_split_pairs.map((p) => String(p[0])) : []);
  };

  const setNum = (k: NumKey, v: string) => {
    setNumInputs((prev) => ({ ...prev, [k]: v }));
    setSaveMsg('');
  };
  const setBool = (k: BoolKey, v: boolean) => {
    setBoolInputs((prev) => ({ ...prev, [k]: v }));
    setSaveMsg('');
  };

  const pageColumnsValue = parseInt(numInputs.page_columns || '', 10);
  const isTwoColumnLayout = pageColumnsValue === 2;

  useEffect(() => {
    (async () => {
      try { setPlatformData(await getPlatformInfo()); } catch {}
    })();
    (async () => {
      try { applyConfig(await gradingGetConfig()); } catch {}
    })();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const num = (k: NumKey, parser: (s: string) => number) =>
        numInputs[k] !== '' ? parser(numInputs[k]) : null;
      const dpi = num('dpi', (s) => parseInt(s, 10));
      const page_columns = num('page_columns', (s) => parseInt(s, 10));
      const column_split_ratio = num('column_split_ratio', parseFloat);
      const force_split = boolInputs.force_split;
      let force_split_pairs: number[][] = [];
      const vlm_temperature = num('vlm_temperature', parseFloat);
      const min_score = num('min_score', parseFloat);
      const iou_threshold = num('iou_threshold', parseFloat);
      if (dpi != null && (isNaN(dpi) || dpi <= 0)) {
        setSaveMsg(t('grading.config.invalidDpi', 'DPI must be a positive integer'));
        return;
      }
      if (page_columns != null && ![1, 2].includes(page_columns)) {
        setSaveMsg(t('grading.config.invalidPageColumns', 'Page columns must be 1 or 2'));
        return;
      }
      if (isTwoColumnLayout && column_split_ratio != null && (isNaN(column_split_ratio) || column_split_ratio <= 0 || column_split_ratio >= 1)) {
        setSaveMsg(t('grading.config.invalidColumnSplitRatio', 'Column split ratio must be between 0 and 1'));
        return;
      }
      if (force_split) {
        for (const raw of splitPagesInput) {
          const text = raw.trim();
          if (!text) continue;
          const n = Number(text);
          if (!Number.isInteger(n) || n <= 0) {
            setSaveMsg(t('grading.config.invalidForceSplitPairs', 'Split pages must be positive integers.'));
            return;
          }
          force_split_pairs.push([n, n + 1]);
        }
      }
      if (vlm_temperature != null && (isNaN(vlm_temperature) || vlm_temperature < 0 || vlm_temperature > 2)) {
        setSaveMsg(t('grading.config.invalidTemp', 'Temperature must be between 0 and 2'));
        return;
      }
      if (min_score != null && (isNaN(min_score) || min_score < 0 || min_score > 1)) {
        setSaveMsg(t('grading.config.invalidMinScore', 'Min score must be between 0 and 1'));
        return;
      }
      if (iou_threshold != null && (isNaN(iou_threshold) || iou_threshold < 0 || iou_threshold > 1)) {
        setSaveMsg(t('grading.config.invalidIou', 'IoU threshold must be between 0 and 1'));
        return;
      }
      const updated = await gradingUpdateConfig({
        dpi,
        page_columns,
        column_split_ratio,
        force_split,
        force_split_pairs,
        contrast_enhance: boolInputs.contrast_enhance,
        contrast_factor: num('contrast_factor', parseFloat),
        max_tokens: num('max_tokens', (s) => parseInt(s, 10)),
        vlm_temperature,
        max_image_pixels: num('max_image_pixels', (s) => parseInt(s, 10)),
        poll_interval: num('poll_interval', (s) => parseInt(s, 10)),
        stable_checks: num('stable_checks', (s) => parseInt(s, 10)),
        idle_timeout: num('idle_timeout', (s) => parseInt(s, 10)),
        min_score,
        sort_boxes: boolInputs.sort_boxes,
        expand_margin: num('expand_margin', (s) => parseInt(s, 10)),
        merge_overlapping: boolInputs.merge_overlapping,
        iou_threshold,
      });
      applyConfig(updated);
      setSaveMsg(t('grading.config.saved', 'Saved. Takes effect on next task.'));
    } catch (e) {
      setSaveMsg(toErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  const numCell = (
    key: NumKey,
    label: string,
    opts: { min?: number; max?: number; step?: number; disabled?: boolean } = {},
  ) => (
    <div className="grading-config-cell">
      <label className="grading-config-label">{label}</label>
      <input
        className="grading-config-input"
        type="number"
        min={opts.min}
        max={opts.max}
        step={opts.step}
        disabled={opts.disabled}
        value={numInputs[key]}
        onChange={(e) => setNum(key, e.target.value)}
      />
    </div>
  );

  const boolCell = (key: BoolKey, label: string) => (
    <label className="grading-config-cell grading-config-checkbox">
      <input
        type="checkbox"
        checked={boolInputs[key]}
        onChange={(e) => setBool(key, e.target.checked)}
      />
      {label}
    </label>
  );

  const pageColumnsCell = () => (
    <div className="grading-config-cell">
      <label className="grading-config-label">{t('grading.config.pageColumns', 'Page Columns')}</label>
      <select
        className="grading-config-input"
        value={numInputs.page_columns}
        onChange={(e) => setNum('page_columns', e.target.value)}
      >
        <option value="1">1</option>
        <option value="2">2</option>
      </select>
    </div>
  );

  const splitPagesCell = () => (
    <div className="grading-config-cell">
      <label className="grading-config-label">{t('grading.config.forceSplitPairs', 'Split After Pages')}</label>
      {splitPagesInput.map((value, idx) => (
        <div key={idx} className="grading-config-pair-row">
          <input
            className="grading-config-input"
            type="number"
            min={1}
            step={1}
            placeholder="3"
            disabled={!boolInputs.force_split}
            value={value}
            onChange={(e) => {
              setSplitPagesInput((prev) => prev.map((v, i) => (i === idx ? e.target.value : v)));
              setSaveMsg('');
            }}
          />
          <button
            type="button"
            className="grading-config-row-remove"
            disabled={!boolInputs.force_split}
            onClick={() => {
              setSplitPagesInput((prev) => prev.filter((_, i) => i !== idx));
              setSaveMsg('');
            }}
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        className="grading-btn grading-btn-secondary grading-config-row-add"
        disabled={!boolInputs.force_split}
        onClick={() => {
          setSplitPagesInput((prev) => [...prev, '']);
          setSaveMsg('');
        }}
      >
        {t('grading.config.forceSplitAdd', '+ Add page')}
      </button>
    </div>
  );

  return (
    <div className="right-panel">
      <Accordion title={t('accordion.configuration', 'Configuration & Metrics')}>
        <div className="configuration-metrics two-column">
          <div className="platform-configuration">
            <h3>{t('accordion.platformConfiguration', 'Platform Configuration')}</h3>
            <p><strong>{t('accordion.processor', 'Processor')}:</strong> {platformData?.Processor || dash}</p>
            <p><strong>{t('accordion.npu', 'NPU')}:</strong> {platformData?.NPU || dash}</p>
            <p><strong>{t('accordion.igpu', 'iGPU')}:</strong> {platformData?.iGPU || dash}</p>
            <p><strong>{t('accordion.memory', 'Memory')}:</strong> {platformData?.Memory || dash}</p>
            <p><strong>{t('accordion.storage', 'Storage')}:</strong> {platformData?.Storage || dash}</p>
          </div>
          <div className="software-performance">
            <h3>{t('accordion.softwareConfiguration', 'Software Configuration')}</h3>
            <p><strong>{t('grading.config.vlmModel', 'VLM Model')}:</strong> {config?.vlm_model || dash}</p>
            <p><strong>{t('grading.config.ocrModel', 'OCR Model')}:</strong> {config?.ocr_model || dash}</p>
            <p><strong>{t('grading.config.layoutModel', 'Layout Model')}:</strong> {config?.layout_model || dash}</p>
          </div>
        </div>
      </Accordion>

      <Accordion title={t('grading.config.title', 'Grading Configuration')}>
        <div className="grading-config-form">
          <div className="grading-config-group">
            <h4 className="grading-config-group-title">{t('grading.config.imageGroup', 'Image Rendering')}</h4>
            <div className="grading-config-grid">
              {pageColumnsCell()}
              {numCell('column_split_ratio', t('grading.config.columnSplitRatio', 'Column Split Ratio'), { min: 0.1, max: 0.9, step: 0.01, disabled: !isTwoColumnLayout })}
              {numCell('dpi', t('grading.config.dpi', 'Render DPI'), { min: 1 })}
              {numCell('contrast_factor', t('grading.config.contrastFactor', 'Contrast Factor'), { min: 0, step: 0.1 })}
              {boolCell('contrast_enhance', t('grading.config.contrastEnhance', 'Contrast Enhance'))}
              {boolCell('force_split', t('grading.config.forceSplit', 'Force Split'))}
              {splitPagesCell()}
            </div>
          </div>

          <div className="grading-config-group">
            <h4 className="grading-config-group-title">{t('grading.config.vlmGroup', 'VLM Parameters')}</h4>
            <div className="grading-config-grid">
              {numCell('vlm_temperature', t('grading.config.vlmTemperature', 'Temperature'), { min: 0, max: 2, step: 0.1 })}
              {numCell('max_tokens', t('grading.config.maxTokens', 'Max Tokens'), { min: 1 })}
              {numCell('max_image_pixels', t('grading.config.maxImagePixels', 'Max Image Pixels'), { min: 1 })}
            </div>
          </div>

          <div className="grading-config-group">
            <h4 className="grading-config-group-title">{t('grading.config.pacingGroup', 'Grading Pace')}</h4>
            <div className="grading-config-grid">
              {numCell('poll_interval', t('grading.config.pollInterval', 'Poll Interval'), { min: 1 })}
              {numCell('stable_checks', t('grading.config.stableChecks', 'Stable Checks'), { min: 1 })}
              {numCell('idle_timeout', t('grading.config.idleTimeout', 'Idle Timeout'), { min: 1 })}
            </div>
          </div>

          <div className="grading-config-group">
            <h4 className="grading-config-group-title">{t('grading.config.detectionGroup', 'Layout Detection')}</h4>
            <div className="grading-config-grid">
              {numCell('min_score', t('grading.config.minScore', 'Min Score'), { min: 0, max: 1, step: 0.05 })}
              {numCell('expand_margin', t('grading.config.expandMargin', 'Expand Margin'), { min: 0 })}
              {boolCell('sort_boxes', t('grading.config.sortBoxes', 'Sort Boxes'))}
              {boolCell('merge_overlapping', t('grading.config.mergeOverlapping', 'Merge Overlapping'))}
              {numCell('iou_threshold', t('grading.config.iouThreshold', 'IoU Threshold'), { min: 0, max: 1, step: 0.05, disabled: !boolInputs.merge_overlapping })}
            </div>
          </div>

          {saveMsg && (
            <p className="grading-config-msg">{saveMsg}</p>
          )}

          <button
            className="grading-btn grading-btn-primary grading-config-save"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? t('grading.config.saving', 'Saving…') : t('grading.config.save', 'Save')}
          </button>
        </div>
      </Accordion>

    </div>
  );
};

export default GradingRightPanel;
