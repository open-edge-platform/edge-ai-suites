// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// What a live recording needs, asked for at the moment it is started.
//
// This is a form, not an orchestrator: it collects and persists the settings,
// then hands them to the caller. Header owns the session/monitoring/pipeline
// sequence, so there is only one copy of it.
//
// However, it stays open for the whole of that sequence. Bringing a session up
// takes seconds, and closing on the first await left the app looking idle
// while it worked; the caller names each stage through `report` so the wait has
// something to show.

import React, { useEffect, useRef, useState } from 'react';
import Modal from './Modal';
import MicrophoneSelect from '../Inputs/MicrophoneSelect';
import '../../assets/css/UploadFilesModal.css';
import { getAudioDevices, getSettings, saveSettings } from '../../services/api';
import { readCameras, writeCameras, type CameraUrls } from '../../services/cameraStorage';
import {
  canStartRecording,
  pickMicrophone,
  type RecordingSettings,
} from '../../services/recordingSettings';
import { useTranslation } from 'react-i18next';
import type { FeatureGuard } from '../../utils/featureGuards';

interface StartRecordingModalProps {
  isOpen: boolean;
  onClose: () => void;
  featureGuard: FeatureGuard;
  /**
   * Brings the session up. Resolves once the pipelines are live, rejects if it
   * could not start, and calls `report` with the stage it is on — this modal
   * stays open and disabled for the duration either way.
   */
  onStart: (settings: RecordingSettings, report: (message: string) => void) => Promise<void>;
}

const StartRecordingModal: React.FC<StartRecordingModalProps> = ({
  isOpen,
  onClose,
  featureGuard,
  onStart,
}) => {
  const { t } = useTranslation();
  const [microphone, setMicrophone] = useState('');
  const [cameras, setCameras] = useState<CameraUrls>(readCameras);
  const [availableDevices, setAvailableDevices] = useState<string[]>([]);
  // Name and location are not edited here; they are held so saving the
  // microphone can post them back unchanged.
  const [project, setProject] = useState({ name: '', location: '' });
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  // The same fact as `starting`, kept where handleStart can trust it. Two clicks
  // landing in one render both read the state from that render's closure, so
  // both would see false and start two sessions; a ref is already true for the
  // second. `starting` stays, because it is what the render reads.
  const startingRef = useRef(false);
  // The stage `onStart` is on, as reported by the caller.
  const [progress, setProgress] = useState('');
  // Gates the dropdown. MicrophoneSelect fetches the device list itself and
  // auto-selects the first entry when what it was handed is empty, deciding that
  // once from its mount-time props. Mounting it before the saved device is known
  // would let that default overwrite the user's choice.
  const [loaded, setLoaded] = useState(false);

  const hasAudioFeatures =
    featureGuard.hasFeature('asr') ||
    featureGuard.hasFeature('summary') ||
    featureGuard.hasFeature('mindmap') ||
    featureGuard.hasFeature('topic_segmentation') ||
    featureGuard.hasFeature('report');
  const hasVideoAnalyticsFeature = featureGuard.hasFeature('video_analytics');

  // Reloaded on every open: the microphone list changes when hardware is
  // plugged in, and Configuration may have renamed the project since last time.
  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;

    setError(null);
    // Header unmounts this while closed, so a reopen starts from a fresh mount
    // and these are already clear. Reset anyway: the guard on Start is the only
    // thing stopping a second session, and it must not depend on where the
    // component happens to be rendered.
    startingRef.current = false;
    setStarting(false);
    setProgress('');
    setLoaded(false);
    setCameras(readCameras());

    const load = async () => {
      try {
        const [settings, devices] = await Promise.all([
          getSettings(),
          hasAudioFeatures ? getAudioDevices() : Promise.resolve<string[]>([]),
        ]);
        if (cancelled) return;

        setProject({ name: settings.projectName, location: settings.projectLocation });
        setAvailableDevices(devices);
        if (hasAudioFeatures) setMicrophone(pickMicrophone(devices, settings.microphone || ''));
      } catch (e) {
        if (cancelled) return;
        console.error('Failed to load recording settings:', e);
        setAvailableDevices([]);
        setMicrophone('');
      } finally {
        // Even on failure: the dropdown reports "no microphones found" for
        // itself, which beats a placeholder that never resolves.
        if (!cancelled) setLoaded(true);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [isOpen, hasAudioFeatures]);

  const setCamera = (key: keyof CameraUrls) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setCameras((previous) => ({ ...previous, [key]: e.target.value }));

  const canStart = canStartRecording({
    hasAudioFeatures,
    hasVideoAnalyticsFeature,
    microphone,
    cameras,
  });

  // Names only the inputs this build actually asks for, so an audio-only
  // deployment is not told to enter a camera URL it has no field for.
  const missingInputMessage = (() => {
    if (hasAudioFeatures && hasVideoAnalyticsFeature) {
      return t(
        'startRecording.inputRequired',
        'Select a microphone or enter at least one camera URL.'
      );
    }
    if (hasAudioFeatures) return t('startRecording.micRequired', 'Select a microphone.');
    if (hasVideoAnalyticsFeature) {
      return t('startRecording.cameraRequired', 'Enter at least one camera URL.');
    }
    // Neither pipeline is enabled, so there is nothing a live session could do.
    return t('startRecording.nothingEnabled', 'No audio or video features are enabled.');
  })();

  // One place, so a branch added to handleStart cannot leave the button stuck
  // on "Starting…" or the ref latched shut.
  const stopStarting = () => {
    startingRef.current = false;
    setStarting(false);
    setProgress('');
  };

  const handleStart = async () => {
    if (!canStart || startingRef.current) return;
    startingRef.current = true;
    setStarting(true);
    setError(null);
    setProgress(t('startRecording.savingSettings', 'Saving settings…'));

    const trimmed: CameraUrls = {
      front: cameras.front.trim(),
      back: cameras.back.trim(),
      board: cameras.board.trim(),
    };

    // Only on start, so closing the modal after a stray keystroke leaves the
    // remembered settings alone.
    writeCameras(trimmed);

    try {
      // The backend opens the device by this name, so it has to be on disk
      // before the pipeline starts. Name and location go back untouched.
      await saveSettings({
        projectName: project.name,
        projectLocation: project.location,
        microphone,
      });
    } catch (e) {
      // Not fatal on its own — a microphone that is already correct in
      // runtime_config.yaml still records — but the user should know the choice
      // did not stick before the session runs with the old one.
      console.error('Failed to save recording settings:', e);
      setError(t('startRecording.saveFailed', 'Could not save these settings. Try again.'));
      stopStarting();
      return;
    }

    try {
      // Held open for the whole sequence: it is not a live session until this
      // resolves, and closing first made a multi-second startup look like
      // nothing had happened.
      await onStart({ microphone, ...trimmed }, setProgress);
    } catch (e) {
      console.error('Failed to start recording:', e);
      setError(t('errors.failedToStartRecording', 'Failed to start recording'));
      stopStarting();
      return;
    }

    stopStarting();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} closeOnOverlayClick={false}>
      <div className="upload-files-modal">
        <h2>{t('startRecording.title', 'Start Recording')}</h2>
        <hr className="modal-title-line" />
        <div className="modal-body">
          {hasAudioFeatures ? (
            <div className="modal-input-group">
              <label htmlFor="microphone">{t('settings.microphone')}</label>
              {loaded ? (
                <MicrophoneSelect
                  selectedMicrophone={microphone}
                  onChange={setMicrophone}
                  disabled={starting}
                />
              ) : (
                <select disabled>
                  <option>{t('settings.loadingDevices')}</option>
                </select>
              )}
              {loaded && availableDevices.length === 0 && (
                <div className="no-devices-message">{t('settings.noDevicesAvailable')}</div>
              )}
            </div>
          ) : (
            <div className="modal-info-message">{t('settings.audioFeaturesDisabled')}</div>
          )}

          {hasVideoAnalyticsFeature ? (
            <>
              <div className="modal-input-group">
                <label htmlFor="frontCamera">{t('settings.frontCamera')}</label>
                <input
                  type="text"
                  id="frontCamera"
                  value={cameras.front}
                  onChange={setCamera('front')}
                  disabled={starting}
                  placeholder="rtsp://127.0.0.1:9554/front"
                />
              </div>

              <div className="modal-input-group">
                <label htmlFor="backCamera">{t('settings.backCamera')}</label>
                <input
                  type="text"
                  id="backCamera"
                  value={cameras.back}
                  onChange={setCamera('back')}
                  disabled={starting}
                  placeholder="rtsp://127.0.0.1:9554/back"
                />
              </div>

              <div className="modal-input-group">
                <label htmlFor="boardCamera">{t('settings.boardCamera')}</label>
                <input
                  type="text"
                  id="boardCamera"
                  value={cameras.board}
                  onChange={setCamera('board')}
                  disabled={starting}
                  placeholder="rtsp://127.0.0.1:9554/content"
                />
              </div>
            </>
          ) : (
            <div className="modal-info-message">{t('settings.videoAnalyticsDisabled')}</div>
          )}

          {loaded && !canStart && !starting && (
            <div className="modal-hint">{missingInputMessage}</div>
          )}

          {error && <div className="error-message">{error}</div>}
          {progress && (
            <div className="modal-progress" role="status">
              <span className="modal-spinner" aria-hidden="true" />
              {progress}
            </div>
          )}
        </div>
        <div className="modal-actions">
          <button
            onClick={handleStart}
            className="apply-button"
            disabled={!canStart || starting}
          >
            {starting ? t('startRecording.starting', 'Starting...') : t('startRecording.start', 'Start')}
          </button>
        </div>
      </div>
    </Modal>
  );
};

export default StartRecordingModal;
