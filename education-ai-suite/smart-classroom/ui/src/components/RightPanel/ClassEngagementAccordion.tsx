import React, { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import '../../assets/css/ClassEngagementAccordion.css';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import {
  setClassStatistics,
  setStreamingStatus,
  setError,
  clearError,
  clearClassStatistics
} from '../../redux/slices/fetchClassStatistics';
import { getClassStatistics } from '../../services/api';
import Accordion from '../common/Accordion';
import { useTranslation } from 'react-i18next';
import Timeline from './Timeline';
import type { FeatureGuard } from '../../utils/featureGuards';

interface ClassStatisticsAccordionProps {
  featureGuard: FeatureGuard;
}

/** Leaderboard rows shown before the "show all" toggle. */
const TOP_STUDENTS = 5;

const ClassStatisticsAccordion: React.FC<ClassStatisticsAccordionProps> = ({ featureGuard }) => {
  const dispatch = useAppDispatch();

  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const videoAnalyticsActive = useAppSelector(
    (state) => state.ui.videoAnalyticsActive
  );
  const videoPlaybackMode = useAppSelector((state) => state.ui.videoPlaybackMode);
  const videoStatus = useAppSelector((state) => state.ui.videoStatus);

  const { statistics, isStreaming, error, lastUpdated } = useAppSelector(
    (state) => state.classStatistics
  );

  const cleanupRef = useRef<(() => void) | null>(null);
  const { t } = useTranslation();
  const [showAllStudents, setShowAllStudents] = useState(false);

  const handleStreamData = useCallback((data: any) => {
    dispatch(setClassStatistics(data));
  }, [dispatch]);

  const handleStreamError = useCallback((error: Error) => {
    console.error('Stream error:', error);
    dispatch(setError(error.message));
  }, [dispatch]);

  useEffect(() => {
    if (!sessionId || !videoAnalyticsActive) return;

    const startStreaming = async () => {
      try {
        dispatch(clearError());
        dispatch(setStreamingStatus(true));

        const cleanup = await getClassStatistics(
          sessionId,
          handleStreamData,
          handleStreamError
        );

        cleanupRef.current = cleanup;
      } catch (error) {
        console.error('Failed to start streaming:', error);
        dispatch(setError(error instanceof Error ? error.message : 'Unknown error'));
      }
    };

    startStreaming();

    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
      dispatch(setStreamingStatus(false));
    };
  }, [sessionId, videoAnalyticsActive, dispatch, handleStreamData, handleStreamError]);

  // Reset statistics when sessionId changes
  useEffect(() => {
    dispatch(clearClassStatistics());
  }, [sessionId, dispatch]);

  const formatLastUpdated = () => {
    if (!lastUpdated) return '';
    return new Date(lastUpdated).toLocaleTimeString();
  };

  // Once the stream ends the app switches to playback and these numbers become
  // the session's final tally. "Waiting for data" would contradict the stats
  // still on screen, so distinguish playback from the pre-session state.
  // `lastUpdated` is the backstop: if any data arrived, we are never "waiting".
  const hasReceivedData = lastUpdated !== null;
  const isPlayback =
    !isStreaming && (videoPlaybackMode || videoStatus === 'completed' || hasReceivedData);

  const statusLabel = isStreaming
    ? t('classStatistics.live')
    : isPlayback
      ? t('classStatistics.playback')
      : t('classStatistics.waitingForData');

  // Distinct students seen standing, ranked by how often — this is what the
  // leaderboard shows, and it also gives the counts context: `stand_count` on
  // its own can't tell you whether one student stood 12 times or twelve did.
  const rankedStudents = useMemo(
    () => [...(statistics.stand_reid ?? [])].sort((a, b) => b.count - a.count),
    [statistics.stand_reid]
  );

  const topCount = rankedStudents[0]?.count ?? 0;
  const participants = rankedStudents.length;
  const participationPercent =
    statistics.student_count > 0
      ? Math.min(100, Math.round((participants / statistics.student_count) * 100))
      : 0;

  const visibleStudents = showAllStudents ? rankedStudents : rankedStudents.slice(0, TOP_STUDENTS);
  const hasOverflow = rankedStudents.length > TOP_STUDENTS;

  return (
    <Accordion title={t('accordion.classStatistics')}>
      <div className="ce-content">
        {/* Live status — previously computed but never rendered. */}
        <div className="ce-status">
          <span
            className={`ce-status-dot${isStreaming ? ' ce-status-dot--live' : isPlayback ? ' ce-status-dot--playback' : ''
              }`}
          />
          <span className="ce-status-label">{statusLabel}</span>
          {lastUpdated && (
            <span className="ce-status-time">
              {isPlayback
                ? t('classStatistics.finalResults')
                : `${t('classStatistics.lastUpdated')} ${formatLastUpdated()}`}
            </span>
          )}
          {statistics.student_count > 0 && (
            <span className="ce-participation">
              <span className="ce-participation-value">
                {t('classStatistics.participation', { percent: participationPercent })}
              </span>
              <span className="ce-participation-detail">
                {t('classStatistics.participationDetail', {
                  active: participants,
                  total: statistics.student_count,
                })}
              </span>
            </span>
          )}
        </div>

        {error && (
          <div className="ce-error">
            ⚠️ {t('classStatistics.errorLabel')}: {error}
          </div>
        )}

        <div className="ce-tiles">
          <div className="ce-tile">
            <span className="ce-tile-value">{statistics.student_count}</span>
            <span className="ce-tile-label" title={t('classStatistics.studentCount')}>
              {t('classStatistics.students')}
            </span>
          </div>
          <div className="ce-tile">
            <span className="ce-tile-value">{statistics.stand_count}</span>
            <span className="ce-tile-label" title={t('classStatistics.standCount')}>
              {t('classStatistics.stands')}
            </span>
          </div>
          <div className="ce-tile">
            <span className="ce-tile-value">{statistics.raise_up_count}</span>
            <span className="ce-tile-label" title={t('classStatistics.raiseUpCount')}>
              {t('classStatistics.hands')}
            </span>
          </div>
        </div>

        <div>
          <h4 className="ce-section-title">{t('classStatistics.mostActive')}</h4>

          {rankedStudents.length > 0 ? (
            <>
              <div className={`ce-board${showAllStudents ? ' ce-board--scroll' : ''}`}>
                {visibleStudents.map((entry) => (
                  <div className="ce-board-row" key={entry.student_id}>
                    <span
                      className="ce-board-id"
                      title={`${t('classStatistics.studentId')}: ${entry.student_id}`}
                    >
                      {`${t('classStatistics.studentId')}: ${entry.student_id}`}
                    </span>
                    <span className="ce-board-track">
                      {/* Bar length is relative to the most active student. */}
                      <span
                        className="ce-board-bar"
                        style={{
                          width: `${topCount > 0 ? (entry.count / topCount) * 100 : 0}%`,
                        }}
                      />
                    </span>
                    <span className="ce-board-count">{entry.count}</span>
                  </div>
                ))}
              </div>

              {hasOverflow && (
                <button
                  className="ce-board-toggle"
                  onClick={() => setShowAllStudents((prev) => !prev)}
                >
                  {showAllStudents
                    ? t('classStatistics.showTop', { count: TOP_STUDENTS })
                    : t('classStatistics.showAll', { count: rankedStudents.length })}
                </button>
              )}
            </>
          ) : (
            <p className="ce-empty">{t('classStatistics.noData')}</p>
          )}
        </div>

        {featureGuard.hasFeature('asr') && featureGuard.isDiarizationEnabled() && (
          <div className="analytics-section audio-analytics">
            <Timeline />
          </div>
        )}
      </div>
    </Accordion>
  );
};

export default ClassStatisticsAccordion;
