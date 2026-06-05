// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Tv2 } from 'lucide-react';
import LiveStreamTab from './LiveStreamTab';

export default function AnalysisResultsPanel({ lvcRuns = [], onStopLvc }) {
  return (
    <Card className="vms-card flex flex-col py-0">
      <CardHeader className="flex flex-row items-center justify-between gap-3 pb-0 pt-[20px] px-[22px] border-b border-[#EDF0F9]">
        <h2 className="vms-panel-title">
          <span className="vms-panel-icon">
            <Tv2 size={14} className="text-[#0071C5]" />
          </span>
          Analysis Results
          {lvcRuns.length > 0 && (
            <span className="ml-2 inline-flex items-center justify-center w-5 h-5 rounded-full bg-[#0071C5] text-white text-[0.6rem] font-bold">
              {lvcRuns.length}
            </span>
          )}
        </h2>
      </CardHeader>

      <CardContent className="p-[22px] pt-4">
        <LiveStreamTab lvcRuns={lvcRuns} onStopLvc={onStopLvc} />
      </CardContent>
    </Card>
  );
}
