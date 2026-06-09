// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { t } from '@/utils/i18n';
import { Card, CardContent } from '@/components/ui/card';
import { Monitor, Camera, CheckCircle, Cpu } from 'lucide-react';

const CARDS = [
  { id:'nvrs',       labelKey:'statConnectedNvrs',  color:'blue',   icon:Monitor,      valueKey:'nvrs'       },
  { id:'discovered', labelKey:'statDiscoveredCams',  color:'purple', icon:Camera,       valueKey:'discovered' },
  { id:'enabled',    labelKey:'statEnabledCams',     color:'green',  icon:CheckCircle,  valueKey:'enabled'    },
  { id:'analyticsApp',    labelKey:'statActiveAnalyticsApp',   color:'orange', icon:Cpu,          valueKey:'analyticsApp', small:true },
];

/* Gradient classes for the top accent bar — dynamic bg so kept as data */
const BAR_GRADIENT = {
  blue:   'from-[#0071C5] to-[#38B2F4]',
  purple: 'from-[#7B2FBE] to-[#B07EE8]',
  green:  'from-[#0DBF8C] to-[#34D3A9]',
  orange: 'from-[#F59E0B] to-[#FBBF24]',
};

export default function StatCards({ stats = { nvrs:2, discovered:0, enabled:0, analyticsApp:'—' } }) {
  return (
    <section className="grid grid-cols-4 max-[1100px]:grid-cols-2 max-[480px]:grid-cols-1 gap-4">
      {CARDS.map(({ id, labelKey, color, icon:Icon, valueKey, small }) => {
        const value = stats[valueKey] ?? '—';
        return (
          <Card key={id} className="vms-card relative overflow-hidden h-full py-0 cursor-default select-none">
            {/* Gradient top accent bar */}
            <div className={`absolute top-0 left-0 right-0 h-[3px] bg-gradient-to-r ${BAR_GRADIENT[color]}`} />

            <CardContent className="flex items-center gap-4 pt-[22px] pb-[18px] px-5">
              <div className={`vms-stat-icon vms-stat-icon-${color}`}>
                <Icon size={20} strokeWidth={1.8} />
              </div>
              <div className="min-w-0">
                <div className={small ? 'vms-stat-value-sm' : 'vms-stat-value'}>{value}</div>
                <div className="vms-stat-label">{t(labelKey)}</div>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </section>
  );
}
