export interface PatientStatus {
    detected: boolean;
    confidence: number; // 0–1
  }
  
  export interface CaretakerStatus {
    detected: boolean;
    count: number;
    confidence: number; // 0–1
  }
  
  export interface LatchStatus {
    state: 'open' | 'closed' | 'unknown';
    confidence: number; // 0–1
  }
  
  export type WorkflowStepKey =
    | 'shared_window_open'
    | 'pull_up_latched'
    | 'build_cab_latched'
    | 'both_latched';
  
  export interface WorkflowState {
    currentStep: WorkflowStepKey | null;
    completedSteps: WorkflowStepKey[];
    timestamps: Partial<Record<WorkflowStepKey, string>>;
  }
  
  export interface RppgData {
    heartRate: number | null;
    respirationRate: number | null;
    heartRateMin: number | null;
    heartRateMax: number | null;
    confidence: number; // 0–1
    sessionDuration: number; // seconds elapsed
    waveform: number[];       // pulse (HR) waveform samples
    respWaveform: number[];   // respiration waveform samples
  }

  export interface ActionActivity {
    activity: string;
    confidence: number;
  }

  export interface ActionData {
    activities: ActionActivity[];
    top_activity: string;
    top_confidence: number;
    status: 'valid' | 'warming_up' | 'error';
    motion_level?: 'still' | 'low' | 'moderate' | 'high' | 'unknown';
    motion_magnitude?: number;
  }
  
  export interface ModelMetrics {
    name: string;
    fps: number;
    latency: number; // ms
    status: 'running' | 'waiting' | 'error';
    framesProcessed: number;
  }

  export interface PipelineWorkload {
    name: string;
    device: string;
    status: string;
    fps?: number;
    latency_ms?: number;
  }

  export interface PipelinePerformance {
    workloads: PipelineWorkload[];
    pipeline_fps: number;
    decode: string;
  }
  
  export interface NicuState {
    systemStatus: 'initializing' | 'preparing' | 'ready' | 'starting' | 'running' | 'error';
    patient: PatientStatus;
    caretaker: CaretakerStatus;
    latch: LatchStatus;
    workflow: WorkflowState;
    rppg: RppgData;
    action: ActionData;
    models: ModelMetrics[];
    pipelinePerformance: PipelinePerformance;
    frameUrl: string | null;
    fps: number;
    uptime: number; // seconds
  }