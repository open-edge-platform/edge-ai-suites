import React from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { setExpandedSection } from '../../redux/slices/nicuSlice';
import VideoFeed from './VideoFeed';
import DetectionCard from './DetectionCard';
import LatchStatusCard from './LatchStatusCard';
import ActionCard from './ActionCard';
import RppgCard from './RppgCard';
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
  const hasExpanded     = expandedSection !== null;

  // Caretaker detail — backend only sends bool, count is always null
  const caretakerDetail = nicu.caretaker.detected
    ? nicu.caretaker.count !== null
      ? `${nicu.caretaker.count} person${nicu.caretaker.count !== 1 ? 's' : ''}`
      : 'Present'
    : undefined;

  return (
    <div className="nicu-panel-content">
      <div className={`nicu-grid${hasExpanded ? ' nicu-grid--has-expanded' : ''}`}>

        {hasExpanded ? (
          <>
            {/* Expanded video */}
            <div className="nicu-grid__expanded">
              {isVideoExpanded && (
                <VideoFeed
                  frameUrl={nicu.frameUrl}
                  fps={nicu.fps}
                  systemStatus={nicu.systemStatus}
                  patientDetected={nicu.patient.detected}
                  caretakerDetected={nicu.caretaker.detected}
                  caretakerCount={nicu.caretaker.count}
                  latchState={nicu.latch.state}
                  isExpanded={true}
                  panelExpanded={expanded}
                  onExpand={() => handleExpand('video')}
                />
              )}
            </div>

            {/* Collapsed detection row */}
            <div className="nicu-collapsed-row">
              {!isVideoExpanded && (
                <VideoFeed
                  frameUrl={nicu.frameUrl}
                  fps={nicu.fps}
                  systemStatus={nicu.systemStatus}
                  patientDetected={nicu.patient.detected}
                  caretakerDetected={nicu.caretaker.detected}
                  caretakerCount={nicu.caretaker.count}
                  latchState={nicu.latch.state}
                  isExpanded={false}
                  panelExpanded={expanded}
                  onExpand={() => handleExpand('video')}
                />
              )}
              <DetectionCard
                title="Patient"
                icon=""
                detected={nicu.patient.detected}
                confidence={nicu.patient.confidence}
              />
              <DetectionCard
                title="Caretaker"
                icon=""
                detected={nicu.caretaker.detected}
                confidence={nicu.caretaker.confidence}
                detail={caretakerDetail}
              />
              <LatchStatusCard latch={nicu.latch} />
              <ActionCard action={nicu.action} />
            </div>

            {/* rPPG — always below, never expandable */}
            <RppgCard rppg={nicu.rppg} />
          </>
        ) : (
          <>
            <VideoFeed
              frameUrl={nicu.frameUrl}
              fps={nicu.fps}
              systemStatus={nicu.systemStatus}
              patientDetected={nicu.patient.detected}
              caretakerDetected={nicu.caretaker.detected}
              caretakerCount={nicu.caretaker.count}
              latchState={nicu.latch.state}
              isExpanded={false}
              panelExpanded={expanded}
              onExpand={() => handleExpand('video')}
            />

            <span className="nicu-section-label">Detection Status</span>
            <div className="nicu-detection-grid">
              <DetectionCard
                title="Patient"
                icon=""
                detected={nicu.patient.detected}
                confidence={nicu.patient.confidence}
              />
              <DetectionCard
                title="Caretaker"
                icon=""
                detected={nicu.caretaker.detected}
                confidence={nicu.caretaker.confidence}
                detail={caretakerDetail}
              />
              <LatchStatusCard latch={nicu.latch} />
              <ActionCard action={nicu.action} />
            </div>

            <span className="nicu-section-label">Vital Signs</span>
            <RppgCard rppg={nicu.rppg} />
          </>
        )}

      </div>
    </div>
  );
};

export default NicuPanel;