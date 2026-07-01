import React from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setExpandedSection } from '../../redux/slices/nicuSlice';
import VideoFeed from './VideoFeed';
import DetectionCard from './DetectionCard';
import '../../assets/css/NicuPanel.css';

interface NicuPanelProps {
  expanded?: boolean;
}

const NicuPanel: React.FC<NicuPanelProps> = ({ expanded = false }) => {
  const dispatch        = useAppDispatch();
  const nicu            = useAppSelector((state) => state.nicu.data);
  const expandedSection = useAppSelector((state) => state.nicu.expandedSection);

  const handleExpand = (section: 'video') => {
    dispatch(setExpandedSection(section));
  };

  const isVideoExpanded = expandedSection === 'video';

  const detail = nicu.polyp.detected
    ? (nicu.polyp.count > 0 ? `${nicu.polyp.count} polyp${nicu.polyp.count > 1 ? 's' : ''}` : 'Present')
    : undefined;

  return (
    <div className="nicu-panel-content">
      <div className={`nicu-grid${isVideoExpanded ? ' nicu-grid--has-expanded' : ''}`}>
        <VideoFeed
          frameUrl={nicu.frameUrl}
          fps={nicu.fps}
          systemStatus={nicu.systemStatus}
          polypDetected={nicu.polyp.detected}
          polypCount={nicu.polyp.count}
          isExpanded={isVideoExpanded}
          panelExpanded={expanded}
          onExpand={() => handleExpand('video')}
        />

        <span className="nicu-section-label">Detection Status</span>
        <div className="nicu-detection-grid">
          <DetectionCard
            title="Polyp"
            icon="●"
            detected={nicu.polyp.detected}
            confidence={nicu.polyp.detected ? nicu.polyp.confidence : null}
            detail={detail}
          />
        </div>
      </div>
    </div>
  );
};

export default NicuPanel;
