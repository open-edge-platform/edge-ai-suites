import { useEffect, useRef } from 'react';
import { useAppSelector } from '../redux/hooks';
import type { AudioStatus, VideoStatus } from '../redux/slices/uiSlice';

// Statuses that mean a pipeline is still working on something. The gate below
// blocks on exactly these instead of waiting for a whitelist of "finished"
// statuses: the audio/video state machines settle in a lot of different places
// ('complete', 'error', 'ready', 'no-devices', 'no-config', 'idle', 'playback',
// or wherever a stage stopped when its tab was unmounted), and a whitelist that
// misses one leaves the upload button greyed out for the rest of the session.
const AUDIO_BUSY_STATUSES: AudioStatus[] = [
  'processing',
  'transcribing',
  'summarizing',
  'mindmapping',
];

const VIDEO_BUSY_STATUSES: VideoStatus[] = ['starting', 'streaming', 'stopping'];

export type UploadBlocker = 'recording' | 'audio' | 'video' | null;

/**
 * Whether a new upload may start, and what is holding it up. Shared by the
 * header button and the video-panel placeholder button so the two can't drift.
 */
export function useUploadGate(): { isUploadEnabled: boolean; blocker: UploadBlocker } {
  const isRecording = useAppSelector((s) => s.ui.isRecording);
  const audioStatus = useAppSelector((s) => s.ui.audioStatus);
  const videoStatus = useAppSelector((s) => s.ui.videoStatus);
  const videoAnalyticsActive = useAppSelector((s) => s.ui.videoAnalyticsActive);
  const videoAnalyticsLoading = useAppSelector((s) => s.ui.videoAnalyticsLoading);
  const videoAnalyticsStopping = useAppSelector((s) => s.ui.videoAnalyticsStopping);

  const audioBusy = AUDIO_BUSY_STATUSES.includes(audioStatus);
  const videoBusy =
    VIDEO_BUSY_STATUSES.includes(videoStatus) ||
    videoAnalyticsActive ||
    videoAnalyticsLoading ||
    videoAnalyticsStopping;

  const blocker: UploadBlocker = isRecording
    ? 'recording'
    : audioBusy
    ? 'audio'
    : videoBusy
    ? 'video'
    : null;

  // A greyed-out Upload File button used to be undiagnosable from the UI. Log
  // every transition with the inputs behind it, so a stuck gate can be read off
  // the console instead of guessed at.
  const loggedRef = useRef<UploadBlocker | 'init'>('init');
  useEffect(() => {
    if (loggedRef.current === blocker) return;
    loggedRef.current = blocker;
    console.log(
      blocker ? `🔒 Upload gate blocked by: ${blocker}` : '🔓 Upload gate open',
      {
        isRecording,
        audioStatus,
        videoStatus,
        videoAnalyticsActive,
        videoAnalyticsLoading,
        videoAnalyticsStopping,
      },
    );
  }, [
    blocker,
    isRecording,
    audioStatus,
    videoStatus,
    videoAnalyticsActive,
    videoAnalyticsLoading,
    videoAnalyticsStopping,
  ]);

  return { isUploadEnabled: blocker === null, blocker };
}

/** i18n key for the tooltip explaining why uploading is unavailable. */
export function uploadBlockerTooltipKey(blocker: UploadBlocker): string {
  switch (blocker) {
    case 'recording':
      return 'tooltips.uploadDisabledRecording';
    case 'audio':
      return 'tooltips.uploadDisabledAudioBusy';
    case 'video':
      return 'tooltips.uploadDisabledVideoBusy';
    default:
      return 'tooltips.uploadFile';
  }
}
