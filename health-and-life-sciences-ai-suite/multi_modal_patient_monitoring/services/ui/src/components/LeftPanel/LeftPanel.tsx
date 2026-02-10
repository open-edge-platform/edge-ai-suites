import React from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { WORKLOADS, WORKLOAD_CONFIG, type WorkloadId } from '../../constants';
import { setExpandedWorkload } from '../../redux/slices/appSlice';
import WorkloadCard from './WorkloadCard'; // ← Import the component
import '../../assets/css/LeftPanel.css';

const LeftPanel = () => {
  const dispatch = useAppDispatch();
  const expandedWorkload = useAppSelector((state) => state.app.expandedWorkload);
  const workloadStates = useAppSelector((state) => state.services.workloads);

  const handleExpand = (id: WorkloadId) => {
    dispatch(setExpandedWorkload(expandedWorkload === id ? null : id));
  };

  // Helper to safely get workload state
  const getWorkloadState = (id: WorkloadId) => {
    return workloadStates[id] || {
      status: 'idle' as const,
      eventCount: 0,
      latestData: {},
      lastEventTime: null,
      waveform: undefined,
      frameData: undefined,
    };
  };

  const expandedCard = WORKLOADS.find((w) => w.id === expandedWorkload);
  const collapsedCards = WORKLOADS.filter((w) => w.id !== expandedWorkload);

  return (
    <div className="left-panel-content">
      <div className={`workload-grid ${expandedWorkload ? 'has-expanded' : ''}`}>
        {expandedWorkload ? (
          <>
            {/* Expanded Card */}
            {expandedCard && (
              <WorkloadCard
                key={expandedCard.id}
                config={WORKLOAD_CONFIG[expandedCard.id]}
                status={getWorkloadState(expandedCard.id).status}
                eventCount={getWorkloadState(expandedCard.id).eventCount}
                latestVitals={getWorkloadState(expandedCard.id).latestData}
                lastEventTime={getWorkloadState(expandedCard.id).lastEventTime}
                waveform={getWorkloadState(expandedCard.id).waveform}
                frameData={getWorkloadState(expandedCard.id).frameData}
                isExpanded={true}
                onExpand={() => handleExpand(expandedCard.id)}
              />
            )}

            {/* Collapsed Cards Row */}
            <div className="collapsed-cards-row">
              {collapsedCards.map((workload) => {
                const state = getWorkloadState(workload.id);
                return (
                  <WorkloadCard
                    key={workload.id}
                    config={WORKLOAD_CONFIG[workload.id]}
                    status={state.status}
                    eventCount={state.eventCount}
                    latestVitals={state.latestData}
                    lastEventTime={state.lastEventTime}
                    waveform={state.waveform}
                    frameData={state.frameData}
                    isExpanded={false}
                    onExpand={() => handleExpand(workload.id)}
                  />
                );
              })}
            </div>
          </>
        ) : (
          /* All Cards (No Expansion) */
          WORKLOADS.map((workload) => {
            const state = getWorkloadState(workload.id);
            return (
              // Around line 60-80, verify the WorkloadCard props:

              <WorkloadCard
                key={workload.id}
                config={WORKLOAD_CONFIG[workload.id]}
                status={state.status}
                eventCount={state.eventCount}
                latestVitals={state.latestData}
                lastEventTime={state.lastEventTime}
                waveform={state.waveform}
                frameData={state.frameData}
                isExpanded={false}
                onExpand={() => handleExpand(workload.id)}
              />
            );
          })
        )}
      </div>
    </div>
  );
};

export default LeftPanel;