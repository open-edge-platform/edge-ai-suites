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
    dataKeys: ['HR', 'RR', 'SpO2', 'CO2_ET', 'BP_DIA', 'BP_SYS'] as const, // Medical device vitals
    hasWaveform: true,
  },
  {
    id: '3d-pose',
    name: '3D Pose',
    color: '#0071c5',
    description: '3D Body Pose Estimation with joint tracking',
    dataKeys: ['joints', 'confidence', 'activity'] as const, // Pose estimation keys
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
    metrics: ['Heart Rate (BPM)', 'Blood Oxygen (SpO2)', 'Respiratory Rate (RR)'],
    medicalTerms: [
      { term: 'PPG', full: 'Photoplethysmography', definition: 'Optical technique to detect blood volume changes in microvascular tissue' },
      { term: 'rPPG', full: 'Remote Photoplethysmography', definition: 'Camera-based contactless vital signs measurement' },
      { term: 'HR', full: 'Heart Rate', definition: 'Number of heartbeats per minute (bpm)', normalRange: '60-100 bpm' },
      { term: 'RR', full: 'Respiratory Rate', definition: 'Number of breaths per minute (rpm)', normalRange: '12-20 rpm' },
      { term: 'SpO2', full: 'Oxygen Saturation', definition: 'Percentage of oxygen-saturated hemoglobin in blood', normalRange: '95-100%' }
    ]
  },
  {
    id: 'ai-ecg',
    name: 'AI-ECG',
    fullName: 'Artificial Intelligence Enhanced Electrocardiogram',
    description: 'Automated ECG signal analysis with AI-powered arrhythmia detection. Provides real-time cardiac rhythm monitoring and classification.',
    metrics: ['ECG Waveform', 'Arrhythmia Classification', 'Heart Rate Variability (HRV)'],
    medicalTerms: [
      { term: 'ECG/EKG', full: 'Electrocardiogram', definition: 'Recording of electrical activity of the heart over time' },
      { term: 'AI-ECG', full: 'AI-Enhanced ECG', definition: 'Machine learning-based automated ECG interpretation and arrhythmia detection' },
      { term: 'P-wave', full: 'Atrial Depolarization', definition: 'Electrical activity during atrial contraction' },
      { term: 'QRS Complex', full: 'Ventricular Depolarization', definition: 'Electrical activity during ventricular contraction' },
      { term: 'T-wave', full: 'Ventricular Repolarization', definition: 'Recovery phase of the ventricles' },
      { term: 'HRV', full: 'Heart Rate Variability', definition: 'Variation in time intervals between heartbeats' }
    ]
  },
  {
    id: 'mdpnp',
    name: 'MDPnP',
    fullName: 'Medical Device Plug-and-Play',
    description: 'Interoperable medical device integration enabling seamless connection between diverse medical equipment and monitoring systems.',
    metrics: ['Blood Pressure (BP)', 'End-Tidal CO2 (ETCO2)', 'Multi-parameter Monitoring'],
    medicalTerms: [
      { term: 'MDPnP', full: 'Medical Device Plug-and-Play', definition: 'Interoperability standard for medical device integration' },
      { term: 'BP', full: 'Blood Pressure', definition: 'Force of blood against arterial walls', normalRange: '120/80 mmHg' },
      { term: 'BP_SYS', full: 'Systolic Blood Pressure', definition: 'Maximum pressure during heart contraction', normalRange: '90-120 mmHg' },
      { term: 'BP_DIA', full: 'Diastolic Blood Pressure', definition: 'Minimum pressure during heart relaxation', normalRange: '60-80 mmHg' },
      { term: 'CO2_ET/ETCO2', full: 'End-Tidal Carbon Dioxide', definition: 'CO2 concentration at end of exhalation', normalRange: '35-45 mmHg' },
      { term: 'mmHg', full: 'Millimeters of Mercury', definition: 'Unit of pressure measurement' },
      { term: 'SpO2', full: 'Peripheral Oxygen Saturation', definition: 'Oxygen saturation measured by pulse oximeter', normalRange: '95-100%' },
      { term: 'Capnography', full: 'CO2 Monitoring', definition: 'Measurement of CO2 in respiratory gases' }
    ]
  },
  {
    id: '3d-pose',
    name: '3D Pose',
    fullName: '3D Human Pose Estimation',
    description: 'Real-time patient posture and movement tracking. Monitors fall risk, gait analysis, and activity levels using computer vision.',
    metrics: ['Skeletal Joint Tracking', 'Fall Detection', 'Activity Recognition'],
    medicalTerms: [
      { term: '3D Pose', full: '3D Human Pose Estimation', definition: 'Computer vision technique to detect human body position and movement' },
      { term: 'Gait Analysis', full: 'Gait Pattern Assessment', definition: 'Study of walking patterns for mobility evaluation' },
      { term: 'ADL', full: 'Activities of Daily Living', definition: 'Routine activities performed for self-care' },
      { term: 'ROM', full: 'Range of Motion', definition: 'Extent of movement around a joint' },
      { term: 'Fall Risk', full: 'Fall Risk Assessment', definition: 'Evaluation of likelihood of falling incidents' },
      { term: 'Skeletal Tracking', full: 'Joint Position Tracking', definition: 'Real-time monitoring of body joint locations in 3D space' }
    ]
  }
];

export const VITAL_SIGNS_INFO = [
  {
    key: 'HR',
    name: 'Heart Rate',
    fullForm: 'HR - Heart Rate',
    unit: 'bpm (beats per minute)',
    description: 'Number of heartbeats per minute.',
    normalRange: '60-100 bpm for adults at rest',
    criticalLow: '< 60 bpm (Bradycardia)',
    criticalHigh: '> 100 bpm (Tachycardia)'
  },
  {
    key: 'SpO2',
    name: 'Blood Oxygen Saturation',
    fullForm: 'SpO2 - Peripheral Oxygen Saturation',
    unit: '% (percentage)',
    description: 'Percentage of oxygen-saturated hemoglobin in arterial blood.',
    normalRange: '95-100%',
    criticalLow: '< 90% (Hypoxemia)',
    criticalHigh: 'N/A'
  },
  {
    key: 'RR',
    name: 'Respiratory Rate',
    fullForm: 'RR - Respiratory Rate',
    unit: 'rpm (respirations per minute)',
    description: 'Number of breaths per minute.',
    normalRange: '12-20 rpm for adults',
    criticalLow: '< 12 rpm (Bradypnea)',
    criticalHigh: '> 20 rpm (Tachypnea)'
  },
  {
    key: 'BP_SYS',
    name: 'Systolic Blood Pressure',
    fullForm: 'BP_SYS - Systolic Blood Pressure',
    unit: 'mmHg (millimeters of mercury)',
    description: 'Maximum arterial pressure during heart contraction (systole).',
    normalRange: '90-120 mmHg',
    criticalLow: '< 90 mmHg (Hypotension)',
    criticalHigh: '> 140 mmHg (Hypertension)'
  },
  {
    key: 'BP_DIA',
    name: 'Diastolic Blood Pressure',
    fullForm: 'BP_DIA - Diastolic Blood Pressure',
    unit: 'mmHg (millimeters of mercury)',
    description: 'Minimum arterial pressure during heart relaxation (diastole).',
    normalRange: '60-80 mmHg',
    criticalLow: '< 60 mmHg (Hypotension)',
    criticalHigh: '> 90 mmHg (Hypertension)'
  },
  {
    key: 'CO2_ET',
    name: 'End-Tidal CO2',
    fullForm: 'ETCO2 - End-Tidal Carbon Dioxide',
    unit: 'mmHg (millimeters of mercury)',
    description: 'Carbon dioxide concentration at the end of exhalation. Reflects ventilation effectiveness.',
    normalRange: '35-45 mmHg',
    criticalLow: '< 30 mmHg (Hyperventilation)',
    criticalHigh: '> 50 mmHg (Hypoventilation)'
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