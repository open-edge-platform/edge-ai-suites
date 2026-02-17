import React, { useEffect, useRef, useCallback } from 'react';
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
import Timeline from "./Timeline";

const ClassStatisticsAccordion: React.FC = () => {
  const dispatch = useAppDispatch();

  const sessionId = useAppSelector((state) => state.ui.sessionId);
  const videoAnalyticsActive = useAppSelector(
    (state) => state.ui.videoAnalyticsActive
  );

  const { statistics, isStreaming, error, lastUpdated } = useAppSelector(
    (state) => state.classStatistics
  );

  const cleanupRef = useRef<(() => void) | null>(null);
  const { t } = useTranslation();

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

  return (
    <Accordion title={t('accordion.classStatistics')}>
      <div className="accordion-content">
        <div
          className="status-bar"
          style={{
            marginBottom: '10px',
            fontSize: '12px',
            color: '#666',
            display: 'flex',
            alignItems: 'center',
            gap: '15px',
          }}
        >
        </div>

        {error && (
          <div
            style={{
              color: '#d32f2f',
              backgroundColor: '#ffebee',
              padding: '8px 12px',
              borderRadius: '4px',
              marginBottom: '15px',
              fontSize: '14px',
              border: '1px solid #ffcdd2',
            }}
          >
            ⚠️ Error: {error}
          </div>
        )}

        <div style={{ display: 'grid', gap: '8px' }}>
          <p>
            <strong>{t('classStatistics.studentCount')}:</strong>
            <span style={{ marginLeft: '8px', fontSize: '16px', fontWeight: 'bold', color: '#0b0c0c' }}>
              {statistics.student_count}
            </span>
          </p>

          <p>
            <strong>{t('classStatistics.standCount')}:</strong>
            <span style={{ marginLeft: '8px', fontSize: '16px', fontWeight: 'bold', color: '#070707' }}>
              {statistics.stand_count}
            </span>
          </p>

          <p>
            <strong>{t('classStatistics.raiseUpCount')}:</strong>
            <span style={{ marginLeft: '8px', fontSize: '16px', fontWeight: 'bold', color: '#0b0c0c' }}>
              {statistics.raise_up_count}
            </span>
          </p>
        </div>

        <div style={{ marginTop: '15px' }}>
          <h4 style={{ margin: '0 0 10px 0', color: '#333' }}>
            {t('classStatistics.standReIdData')}:
          </h4>

          {statistics.stand_reid.length > 0 ? (
            <ul
              style={{
                margin: '0',
                paddingLeft: '20px',
                maxHeight: '150px',
                overflowY: 'auto',
              }}
            >
              {statistics.stand_reid.map((entry) => (
                <li key={entry.student_id}>
                  <strong>{t('classStatistics.studentId')}:</strong> {entry.student_id}
                  <span style={{ marginLeft: '10px', color: '#666' }}>
                    {t('classStatistics.count')}: {entry.count}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p
              style={{
                fontStyle: 'italic',
                color: '#666',
                padding: '8px',
                backgroundColor: '#f5f5f5',
                borderRadius: '4px',
              }}
            />
          )}
        </div>
        <div className="analytics-section audio-analytics" style={{ margin: '20px 2px 3px 4px', color: '#388e3c',  }}>
          <Timeline />
        </div>
      </div>
    </Accordion>
  );
};

export default ClassStatisticsAccordion;
