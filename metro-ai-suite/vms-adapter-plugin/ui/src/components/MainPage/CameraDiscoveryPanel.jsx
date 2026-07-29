// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { ScanLine } from 'lucide-react';
import { t } from '@/utils/i18n';
import { VmsShimFactory } from '@/services/shims';

const STATUS_BADGE_CLS = {
  online:  'vms-badge vms-badge-green',
  offline: 'vms-badge vms-badge-red',
  unknown: 'vms-badge vms-badge-gray',
};

const DOT_CLS = {
  online:  'vms-dot vms-dot-online animate-pulse-dot',
  offline: 'vms-dot vms-dot-offline',
  unknown: 'vms-dot vms-dot-unknown',
};

export default function CameraDiscoveryPanel({ cameras = [], onDiscover, onToggle, discovering = false }) {
  return (
    <Card className="vms-card flex flex-col py-0">
      {/* Header */}
      <CardHeader className="vms-panel-hdr">
        <div className="flex flex-col gap-[5px]">
          <h2 className="vms-panel-title">
            <span className="vms-panel-icon">
              <ScanLine size={15} className="text-[#0071C5]" />
            </span>
            {t('cameraPanelTitle')}
          </h2>
          <p className="text-[0.72rem] text-[#A3B0CC] pl-[39px]">
            {cameras.length > 0
              ? `${cameras.length} cameras found across connected NVRs`
              : t('cameraDiscoverHint')}
          </p>
        </div>
        <Button
          size="sm"
          className="btn-primary text-white shrink-0 text-[0.78rem] font-semibold px-4"
          onClick={onDiscover}
          disabled={discovering}
        >
          <ScanLine size={13} className="mr-[6px]" />
          {discovering ? t('cameraDiscovering') : cameras.length > 0 ? t('cameraRediscover') : t('cameraDiscover')}
        </Button>
      </CardHeader>

      {/* Table */}
      <CardContent className="p-0 flex-1 overflow-auto max-h-[400px]">
        <Table>
          <TableHeader>
            <TableRow className="border-0 hover:bg-transparent">
              {[t('cameraColId'), t('cameraColName'), t('cameraColVendor'), t('cameraColStatus'), t('cameraEnable')].map((h, i) => (
                <TableHead key={h} className={`vms-th ${i === 4 ? 'text-center' : ''}`}>{h}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {cameras.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={5}>
                  <div className="vms-empty">
                    <ScanLine size={32} strokeWidth={1.2} className="text-[#C8D2E8]" />
                    <span>Click <strong className="text-[#6B7BA4]">Discover Cameras</strong> to populate the camera list</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              cameras.map((cam, idx) => (
                <TableRow
                  key={cam.camera_id}
                  className={`vms-tr ${idx % 2 === 0 ? 'vms-tr-even' : 'vms-tr-odd'}`}
                >
                  <TableCell className="vms-td-mono">{cam.camera_id}</TableCell>
                  <TableCell className="vms-td">
                    <div className="flex items-center gap-2">
                      <span className={DOT_CLS[cam.status] ?? DOT_CLS.unknown} />
                      <span className="font-semibold text-[#0E1C47] text-[0.84rem]">{cam.camera_name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="vms-td">
                    <span className={VmsShimFactory.create(cam.vendor).badgeCls}>
                      {VmsShimFactory.create(cam.vendor).label}
                    </span>
                  </TableCell>
                  <TableCell className="vms-td">
                    <span className={`${STATUS_BADGE_CLS[cam.status] ?? STATUS_BADGE_CLS.unknown} capitalize`}>
                      {cam.status}
                    </span>
                  </TableCell>
                  <TableCell className="vms-td text-center">
                    <Switch
                      checked={cam.enabled}
                      onCheckedChange={(checked) => onToggle?.(cam.camera_id, checked)}
                      className="data-[state=checked]:bg-[#0071C5]"
                    />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
