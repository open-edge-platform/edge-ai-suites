import React, { useEffect, useState } from 'react';
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

  const [dpiInput, setDpiInput] = useState<string>('');
  const [tempInput, setTempInput] = useState<string>('');
  const [pollInput, setPollInput] = useState<string>('');
  const [checksInput, setChecksInput] = useState<string>('');
  const [timeoutInput, setTimeoutInput] = useState<string>('');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string>('');

  useEffect(() => {
    (async () => {
      try { setPlatformData(await getPlatformInfo()); } catch {}
    })();
    (async () => {
      try {
        const cfg = await gradingGetConfig();
        setConfig(cfg);
        setDpiInput(cfg.dpi != null ? String(cfg.dpi) : '');
        setTempInput(cfg.vlm_temperature != null ? String(cfg.vlm_temperature) : '');
        setPollInput(cfg.poll_interval != null ? String(cfg.poll_interval) : '');
        setChecksInput(cfg.stable_checks != null ? String(cfg.stable_checks) : '');
        setTimeoutInput(cfg.idle_timeout != null ? String(cfg.idle_timeout) : '');
      } catch {}
    })();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const dpi = dpiInput !== '' ? parseInt(dpiInput, 10) : null;
      const vlm_temperature = tempInput !== '' ? parseFloat(tempInput) : null;
      if (dpiInput !== '' && (isNaN(dpi!) || dpi! <= 0)) {
        setSaveMsg(t('grading.config.invalidDpi', 'DPI must be a positive integer'));
        return;
      }
      if (tempInput !== '' && (isNaN(vlm_temperature!) || vlm_temperature! < 0 || vlm_temperature! > 2)) {
        setSaveMsg(t('grading.config.invalidTemp', 'Temperature must be between 0 and 2'));
        return;
      }
      const poll_interval = pollInput !== '' ? parseInt(pollInput, 10) : null;
      const stable_checks = checksInput !== '' ? parseInt(checksInput, 10) : null;
      const idle_timeout = timeoutInput !== '' ? parseInt(timeoutInput, 10) : null;
      const updated = await gradingUpdateConfig({ dpi, vlm_temperature, poll_interval, stable_checks, idle_timeout });
      setConfig(updated);
      setPollInput(updated.poll_interval != null ? String(updated.poll_interval) : '');
      setChecksInput(updated.stable_checks != null ? String(updated.stable_checks) : '');
      setTimeoutInput(updated.idle_timeout != null ? String(updated.idle_timeout) : '');
      setSaveMsg(t('grading.config.saved', 'Saved. Takes effect on next task.'));
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

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
        </div>
      </Accordion>

      <Accordion title={t('grading.config.title', 'Grading Configuration')}>
        <div className="grading-config-form">
          <div className="grading-config-row">
            <label className="grading-config-label">{t('grading.config.dpi', 'Render DPI')}</label>
            <input
              className="grading-config-input"
              type="number"
              min={1}
              value={dpiInput}
              onChange={(e) => { setDpiInput(e.target.value); setSaveMsg(''); }}
            />
          </div>

          <div className="grading-config-row">
            <label className="grading-config-label">{t('grading.config.vlmTemperature', 'Temperature')}</label>
            <input
              className="grading-config-input"
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={tempInput}
              onChange={(e) => { setTempInput(e.target.value); setSaveMsg(''); }}
            />
          </div>

          <div className="grading-config-row">
            <label className="grading-config-label">{t('grading.config.pollInterval', 'Poll Interval')}</label>
            <input
              className="grading-config-input"
              type="number"
              min={1}
              value={pollInput}
              onChange={(e) => { setPollInput(e.target.value); setSaveMsg(''); }}
            />
          </div>

          <div className="grading-config-row">
            <label className="grading-config-label">{t('grading.config.stableChecks', 'Stable Checks')}</label>
            <input
              className="grading-config-input"
              type="number"
              min={1}
              value={checksInput}
              onChange={(e) => { setChecksInput(e.target.value); setSaveMsg(''); }}
            />
          </div>

          <div className="grading-config-row">
            <label className="grading-config-label">{t('grading.config.idleTimeout', 'Idle Timeout')}</label>
            <input
              className="grading-config-input"
              type="number"
              min={1}
              value={timeoutInput}
              onChange={(e) => { setTimeoutInput(e.target.value); setSaveMsg(''); }}
            />
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
