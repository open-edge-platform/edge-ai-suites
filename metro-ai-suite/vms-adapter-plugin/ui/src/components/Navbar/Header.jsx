// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { t } from '@/utils/i18n';

export default function Header({ engineStatus = 'connected' }) {
  const dotColor = {
    connected: 'bg-[#0DBF8C] animate-pulse-dot',
    degraded:  'bg-[#F59E0B]',
    offline:   'bg-[#EF4444]',
  }[engineStatus] ?? 'bg-[#0DBF8C]';

  const statusStyle = {
    connected: { label: t('statusConnected'), cls: 'text-[#0DBF8C] bg-[#0DBF8C]/10 px-2 py-[2px]' },
    degraded:  { label: t('statusDegraded'),  cls: 'text-[#F59E0B] bg-[#F59E0B]/10 px-2 py-[2px]' },
    offline:   { label: t('statusOfflineEngine'), cls: 'text-[#EF4444] bg-[#EF4444]/10 px-2 py-[2px]' },
  }[engineStatus] ?? { label: t('statusConnected'), cls: 'text-[#0DBF8C]' };

  return (
    <header className="vms-header">
      <div className="vms-header-accent" />

      {/* Brand */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="vms-brand-icon">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <rect x="2" y="2" width="5" height="5" rx="1" fill="white" opacity="0.9"/>
            <rect x="9" y="2" width="5" height="5" rx="1" fill="white" opacity="0.6"/>
            <rect x="2" y="9" width="5" height="5" rx="1" fill="white" opacity="0.6"/>
            <rect x="9" y="9" width="5" height="5" rx="1" fill="white" opacity="0.9"/>
          </svg>
        </div>
        <div className="flex flex-col leading-none">
          <span className="text-white font-bold text-[1rem] tracking-[-0.3px]">{t('appTitle')}</span>
          <span className="text-[#4A9ED6] text-[0.7rem] font-medium mt-[2px]">Open Edge Platform Analytics Engine</span>
        </div>
      </div>

      {/* Engine status badge — center */}
      <div className="flex-1 flex justify-center">
        <div className="vms-engine-pill">
          <span className={`w-[7px] h-[7px] rounded-full shrink-0 shadow-[0_0_0_2px_rgba(255,255,255,0.08)] ${dotColor}`} />
          <span className="text-white/50 text-[0.73rem]">Analytics Engine</span>
          <span className="text-white font-semibold">Open Edge Platform</span>
          <span className={`text-[0.69rem] font-bold uppercase tracking-[0.6px] ${statusStyle.cls}`}>
            {statusStyle.label}
          </span>
        </div>
      </div>

      {/* Right spacer */}
      <div className="shrink-0 w-[210px]" />
    </header>
  );
}
