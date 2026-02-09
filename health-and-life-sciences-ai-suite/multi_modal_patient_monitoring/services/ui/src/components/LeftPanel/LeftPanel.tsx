// src/components/LeftPanel/LeftPanel.tsx
import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '../../redux/hooks';
import { WORKLOADS, type WorkloadId } from '../../constants';
import { setExpandedWorkload } from '../../redux/slices/appSlice';
import WorkloadCard from './WorkloadCard';
import '../../assets/css/LeftPanel.css';

const LeftPanel = () => {
  const dispatch = useAppDispatch();
  const expandedWorkload = useAppSelector((state) => state.app.expandedWorkload);
  const workloadStates = useAppSelector((state) => state.services.workloads);

  const handleExpand = (id: WorkloadId) => {
    dispatch(setExpandedWorkload(expandedWorkload === id ? null : id));
  };


  return (
    <div className="left-panel">
      <div className={`workload-grid ${expandedWorkload ? 'has-expanded' : ''}`}>
        {WORKLOADS.map((workload) => {
          const state = workloadStates[workload.id];
          const isExpanded = expandedWorkload === workload.id;

          return (
            <WorkloadCard
              key={workload.id}
              config={workload}
              status={state?.status || 'idle'}
              eventCount={state?.eventCount || 0}
              latestVitals={state?.latestData || workload.mockVitals}
              lastEventTime={state?.lastEventTime || null}
              isExpanded={isExpanded}
              onExpand={() => handleExpand(workload.id)}
            />
          );
        })}
      </div>
    </div>
  );
};

export default LeftPanel;