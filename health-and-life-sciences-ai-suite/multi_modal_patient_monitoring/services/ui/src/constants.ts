// src/constants.ts
export const constants = {
  PROJECT_NAME: 'Health AI Suite',
  TITLE: 'Health & Life Sciences AI Suite',
  COPYRIGHT: '© 2026 Intel Corporation. All rights reserved.',
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
    name: 'MD PnP',
    color: '#0071c5',
    description: 'Medical Device Plug-and-Play Integration',
    dataKeys: ['HR', 'RR', 'SpO2', 'CO2_ET', 'BP_DIA', 'BP_SYS'] as const, // Medical device vitals
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

export const WORKLOAD_INFO = [
  {
    id: 'rppg',
    name: 'rPPG',
    fullName: 'Remote Photoplethysmography',
    description: 'Non-contact heart rate and vital signs monitoring using standard RGB cameras. Detects blood flow through subtle skin color changes.',
    metrics: ['Heart Rate (BPM)', 'Respiratory Rate (RR)'],
    medicalTerms: [
      { term: 'rPPG', full: 'Remote Photoplethysmography' },
      { term: 'HR', full: 'Heart Rate' },
      { term: 'RR', full: 'Respiratory Rate' },
    ]
  },
  {
    id: 'ai-ecg',
    name: 'AI-ECG',
    fullName: 'Artificial Intelligence Enhanced Electrocardiogram',
    description: 'Automated ECG signal analysis with AI-powered arrhythmia detection. Provides real-time cardiac rhythm monitoring and classification.',
    metrics: ['ECG Waveform', 'Arrhythmia Classification', 'Heart Rate Variability (HRV)'],
    medicalTerms: [
      { term: 'ECG/EKG', full: 'Electrocardiogram' },
      { term: 'AI-ECG', full: 'AI-Enhanced ECG' },
      { term: 'P-wave', full: 'Atrial Depolarization' },
      { term: 'QRS Complex', full: 'Ventricular Depolarization' },
      { term: 'T-wave', full: 'Ventricular Repolarization' },
      { term: 'HRV', full: 'Heart Rate Variability' }
    ]
  },
  {
    id: 'mdpnp',
    name: 'MD PnP',
    fullName: 'Medical Device Plug-and-Play',
    description: 'Interoperable medical device integration enabling seamless connection between diverse medical equipment and monitoring systems.',
    metrics: ['Blood Pressure (BP)', 'End-Tidal CO2 (ETCO2)', 'Multi-parameter Monitoring'],
    medicalTerms: [
      { term: 'MD PnP', full: 'Medical Device Plug-and-Play' },
      { term: 'BP', full: 'Blood Pressure' },
      { term: 'BP_SYS', full: 'Systolic Blood Pressure' },
      { term: 'BP_DIA', full: 'Diastolic Blood Pressure' },
      { term: 'CO2_ET/ETCO2', full: 'End-Tidal Carbon Dioxide' },
      { term: 'mmHg', full: 'Millimeters of Mercury' },
      { term: 'SpO2', full: 'Peripheral Oxygen Saturation' },
      { term: 'Capnography', full: 'CO2 Monitoring' }
    ]
  },
  {
    id: '3d-pose',
    name: '3D Pose',
    fullName: '3D Human Pose Estimation',
    description: 'Real-time patient posture and movement tracking. Monitors fall risk, gait analysis, and activity levels using computer vision.',
    metrics: ['Skeletal Joint Tracking', 'Fall Detection', 'Activity Recognition'],
    medicalTerms: [
      { term: '3D Pose', full: '3D Human Pose Estimation' },
      { term: 'Gait Analysis', full: 'Gait Pattern Assessment' },
      { term: 'ADL', full: 'Activities of Daily Living' },
      { term: 'ROM', full: 'Range of Motion' },
      { term: 'Fall Risk', full: 'Fall Risk Assessment' },
      { term: 'Skeletal Tracking', full: 'Joint Position Tracking' }
    ]
  }
];


export const MEDICAL_UNITS = [
  { unit: 'bpm', fullForm: 'Beats Per Minute', usage: 'Heart rate measurement' },
  { unit: 'rpm', fullForm: 'Respirations Per Minute', usage: 'Respiratory rate measurement' },
  { unit: 'mmHg', fullForm: 'Millimeters of Mercury', usage: 'Blood pressure and CO2 measurement' },
  { unit: '%', fullForm: 'Percentage', usage: 'Oxygen saturation (SpO2)' },
  { unit: 'Hz', fullForm: 'Hertz (cycles per second)', usage: 'Waveform sampling frequency' }
];

export const ECG_CLASSIFICATIONS = [
  { code: 'N', name: 'Normal Sinus Rhythm', description: 'Regular heart rhythm with normal P-QRS-T pattern' },
  { code: 'AF', name: 'Atrial Fibrillation', description: 'Irregular, rapid atrial activity without distinct P-waves' },
  { code: 'O', name: 'Other Rhythm', description: 'Any rhythm not classified as Normal or Atrial Fibrillation' },
  { code: '~', name: 'Too Noisy', description: 'Signal quality too poor for accurate classification' }
];