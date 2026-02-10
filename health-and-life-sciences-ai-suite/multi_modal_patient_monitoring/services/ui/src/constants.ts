// src/constants.ts
export const constants = {
  PROJECT_NAME: 'Health AI Suite',
  TITLE: 'Health & Life Sciences AI Suite',
  COPYRIGHT: '© 2024 Intel Corporation. All rights reserved.',
  VERSION: 'v1.0.0',
};

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001';

export const WORKLOADS = [
  {
    id: 'rppg',
    name: 'rPPG',
    color: '#0071c5',
    description: 'Remote Photoplethysmography - Heart Rate & Respiratory Rate',
    dataKeys: ['HR', 'RR'] as const, // Expected vital keys
    hasWaveform: true,
  },
  {
    id: 'ai-ecg',
    name: 'AI-ECG',
    color: '#0071c5',
    description: 'AI-powered ECG Analysis with 12-lead classification',
    dataKeys: ['prediction', 'filename'] as const, // AI prediction keys
    hasWaveform: true,
  },
  {
    id: 'mdpnp',
    name: 'MDPNP',
    color: '#0071c5',
    description: 'Medical Device Plug-and-Play Integration',
    dataKeys: ['HR', 'CO2_ET', 'BP_DIA'] as const, // Medical device vitals
    hasWaveform: true,
  },
  {
    id: '3d-pose',
    name: '3D Pose',
    color: '#0071c5',
    description: '3D Body Pose Estimation with joint tracking',
    dataKeys: ['activity'] as const, // Pose estimation keys
    hasWaveform: false,
  },
] as const;

export type WorkloadId = typeof WORKLOADS[number]['id'];

export const WORKLOAD_CONFIG = WORKLOADS.reduce((acc, w) => {
  acc[w.id] = w;
  return acc;
}, {} as Record<WorkloadId, typeof WORKLOADS[number]>);