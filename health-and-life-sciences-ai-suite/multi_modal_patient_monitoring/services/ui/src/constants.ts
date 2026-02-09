// src/constants.ts
export const constants = {
  PROJECT_NAME: 'Health AI Suite',
  TITLE: 'Health & Life Sciences AI Suite',
  COPYRIGHT: '© 2024 Intel Corporation. All rights reserved.',
  VERSION: 'v1.0.0',
};

export const WORKLOADS = [
  { 
    id: 'rppg', 
    name: 'RPPG', 
    icon: '❤️', 
    color: '#e74c3c',
    description: 'Remote Photoplethysmography',
    mockVitals: { HR: 72, RR: 14 }
  },
  { 
    id: 'ai-ecg', 
    name: 'AI-ECG', 
    icon: '📊', 
    color: '#3498db',
    description: 'AI-powered ECG Analysis',
    mockVitals: { QRS: 90, PR: 160 }
  },
  { 
    id: 'mdpnp', 
    name: 'MDPNP', 
    icon: '🩺', 
    color: '#f39c12',
    description: 'Medical Device Integration',
    mockVitals: { BP_SYS: 120, BP_DIA: 80 }
  },
  { 
    id: '3d-pose', 
    name: '3D Pose', 
    icon: '🧍', 
    color: '#9b59b6',
    description: '3D Body Pose Estimation',
    mockVitals: { joints: 25, confidence: 0.92 }
  },
] as const;

export type WorkloadId = typeof WORKLOADS[number]['id'];