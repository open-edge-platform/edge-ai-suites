import React from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setExpandedSection } from '../../redux/slices/detectionSlice';
import VideoFeed from './VideoFeed';
import DetectionCard from './DetectionCard';
import '../../assets/css/DetectionPanel.css';

interface DetectionPanelProps {
  expanded?: boolean;
}

const DetectionPanel: React.FC<DetectionPanelProps> = ({ expanded = false }) => {
  const dispatch        = useAppDispatch();
  const detection            = useAppSelector((state) => state.detection.data);
  const expandedSection = useAppSelector((state) => state.detection.expandedSection);

  const handleExpand = (section: 'video') => {
    dispatch(setExpandedSection(section));
  };

  const isVideoExpanded = expandedSection === 'video';

  const detail = detection.polyp.detected
    ? (detection.polyp.count > 0 ? `${detection.polyp.count} polyp${detection.polyp.count > 1 ? 's' : ''}` : 'Present')
    : undefined;

  return (
    <div className="det-panel-content">
      <div className={`det-grid${isVideoExpanded ? ' det-grid--has-expanded' : ''}`}>
        <VideoFeed
          frameUrl={detection.frameUrl}
          fps={detection.fps}
          systemStatus={detection.systemStatus}
          isExpanded={isVideoExpanded}
          panelExpanded={expanded}
          onExpand={() => handleExpand('video')}
        />

        <span className="det-section-label">Detection Status</span>
        <div className="det-detection-grid">
          <DetectionCard
            title="Polyp"
            icon="●"
            detected={detection.polyp.detected}
            confidence={detection.polyp.detected ? detection.polyp.confidence : null}
            detail={detail}
            hero
            sessionDistinctPolyps={detection.polyp.distinct_polyps}
            sessionFramesProcessed={detection.polyp.frames_processed}
            sessionFramesWithDetection={detection.polyp.frames_with_detection}
            sessionRate={detection.polyp.detection_rate}
            sessionPeakConfidence={detection.polyp.peak_confidence}
            sessionSeconds={detection.polyp.session_seconds}
          />
        </div>
      </div>
    </div>
  );
};

export default DetectionPanel;
