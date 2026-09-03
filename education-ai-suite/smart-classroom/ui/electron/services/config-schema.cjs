// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Allowlist of settings the UI may change.
//
// This is the security boundary for config writes: the renderer can only name a
// path that appears here, and the value is type/range checked before it reaches
// the YAML document. Anything else is rejected, so the settings screen can never
// be used to inject arbitrary keys into a file that drives model loading and
// subprocess launches.
//
// Deliberately excluded, and not to be added without thinking it through:
// host addresses and ports, filesystem paths that feed subprocess launches,
// model identifiers resolved against a hub, and the telegram / scp_sender
// integration blocks.
//
// A field belongs to a GROUP, which is the feature a user would go looking
// under, and to a SUBGROUP, which names the exact config.yaml node it lives in.
// Subgroups are what keep the two structures honest: if a field's path does not
// start with its subgroup's node, one of the two is wrong.
//
// Field labels are intentionally plain English rather than i18n keys: they name
// technical config paths, and the path itself is shown next to each control.

const CONFIG = 'config'; // config.yaml
const RUNTIME = 'runtime'; // runtime_config.yaml
const PROXY = 'proxy'; // .proxy-config (JSON)

const FEATURE_LABELS = {
  asr: 'Speech recognition',
  summary: 'Summary',
  mindmap: 'Mind map',
  topic_segmentation: 'Topic segmentation',
  video_analytics: 'Video analytics',
  board_ocr: 'Board OCR',
  content_search: 'Content search',
  qa: 'Question answering',
  grading: 'Grading',
  report: 'Report',
};

// The "Get started" screen shows `wizard: true` only; the full editor still
// shows everything.
const featureFields = Object.entries(FEATURE_LABELS).map(([id, label]) => ({
  path: `features.${id}.enabled`,
  file: CONFIG,
  group: 'features',
  label,
  type: 'boolean',
  wizard: true,
}));

const GROUPS = [
  { id: 'features', label: 'Features' },
  { id: 'general', label: 'General' },
  { id: 'asr', label: 'Speech recognition' },
  { id: 'audio', label: 'Audio processing' },
  { id: 'summarization', label: 'Summarization and topics' },
  { id: 'devices', label: 'Models and devices' },
  { id: 'videoAnalytics', label: 'Video analytics' },
  { id: 'contentSearch', label: 'Content search' },
  { id: 'report', label: 'Report' },
  { id: 'project', label: 'Project' },
  { id: 'proxy', label: 'Proxy' },
];

// `node` is the config.yaml path the subgroup mirrors, shown under the heading.
// Order here is the order the sections render in. Groups whose fields all come
// from one node (features, report, project, proxy) have no subgroup at all.
const SUBGROUPS = [
  { id: 'asrRecognition', group: 'asr', label: 'Recognition', node: 'models.asr' },
  { id: 'asrDiarization', group: 'asr', label: 'Speaker diarization', node: 'models.diarization' },

  { id: 'audioChunking', group: 'audio', label: 'Chunking', node: 'audio_preprocessing' },
  { id: 'audioUploads', group: 'audio', label: 'Uploads', node: 'audio_util' },
  { id: 'audioCleanup', group: 'audio', label: 'Cleanup', node: 'pipeline' },

  { id: 'summarizer', group: 'summarization', label: 'Summarizer', node: 'models.summarizer' },
  { id: 'promptChunking', group: 'summarization', label: 'Prompt chunking', node: 'models.text_gen.chunking' },
  {
    id: 'topicSegmentation',
    group: 'summarization',
    label: 'Topic segmentation',
    node: 'models.text_gen.segmentation',
  },
  { id: 'mindmap', group: 'summarization', label: 'Mind map', node: 'mindmap' },

  { id: 'textGen', group: 'devices', label: 'Text generation', node: 'models.text_gen' },
  { id: 'ocr', group: 'devices', label: 'OCR', node: 'models.ocr' },

  { id: 'poseModels', group: 'videoAnalytics', label: 'Pose models', node: 'models.va' },
  { id: 'streaming', group: 'videoAnalytics', label: 'Streaming', node: 'va_pipeline' },
  {
    id: 'poseStatistics',
    group: 'videoAnalytics',
    label: 'Pose statistics',
    node: 'va_pipeline.pose_statistics',
  },
  { id: 'boardOcr', group: 'videoAnalytics', label: 'Board OCR', node: 'board_ocr' },

  { id: 'csGeneral', group: 'contentSearch', label: 'General', node: 'content_search' },
  { id: 'csStorage', group: 'contentSearch', label: 'Storage', node: 'content_search.storage' },
  { id: 'csIngest', group: 'contentSearch', label: 'File ingest', node: 'content_search.file_ingest' },
  {
    id: 'csParser',
    group: 'contentSearch',
    label: 'Document parser',
    node: 'content_search.file_ingest.document_parser',
  },
  { id: 'csReranker', group: 'contentSearch', label: 'Reranker', node: 'content_search.file_ingest.reranker' },
  {
    id: 'csVideoPreprocess',
    group: 'contentSearch',
    label: 'Video preprocessing',
    node: 'content_search.video_preprocess',
  },
  { id: 'csQa', group: 'contentSearch', label: 'Question answering', node: 'content_search.qa' },
];

const FIELDS = [
  ...featureFields,

  // -------------------------------------------------------------------------
  // General
  // -------------------------------------------------------------------------
  { path: 'app.language', file: CONFIG, group: 'general', label: 'Language', type: 'enum', options: ['en', 'zh'], wizard: true },
  {
    path: 'app.cleanup_on_exit',
    file: CONFIG,
    group: 'general',
    label: 'Clean up temporary files on exit',
    type: 'boolean',
  },
  {
    path: 'models.model_hub',
    file: CONFIG,
    group: 'general',
    label: 'Model hub',
    type: 'enum',
    options: ['huggingface', 'modelscope'],
    help: 'Where models are downloaded from.',
  },

  // -------------------------------------------------------------------------
  // Speech recognition
  // -------------------------------------------------------------------------
  {
    path: 'models.asr.provider',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'ASR provider',
    type: 'enum',
    options: ['openai', 'openvino', 'funasr'],
    wizard: true,
    help: 'openai suits English; funasr suits Chinese.',
  },
  {
    path: 'models.asr.name',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'ASR model',
    type: 'string',
    maxLength: 128,
    wizard: true,
    // The setup script's picks; free text stays allowed for anything else.
    suggestions: ['whisper-base', 'whisper-small', 'whisper-medium', 'whisper-large', 'paraformer-zh'],
    help: 'whisper-small is the balanced default; paraformer-zh is Chinese-optimised.',
  },
  {
    path: 'models.asr.device',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'ASR device',
    type: 'enum',
    options: ['CPU', 'GPU', 'NPU'],
    wizard: true,
  },
  {
    path: 'models.asr.diarization',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'Speaker diarization',
    type: 'boolean',
    wizard: true,
    help: 'Turns diarization on; tune it under Speaker diarization below.',
  },
  {
    path: 'models.asr.hf_token',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'Hugging Face token',
    type: 'secret',
    maxLength: 256,
    wizard: true,
    help: 'Required only when diarization is enabled.',
  },
  {
    path: 'models.asr.temperature',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'Decoding temperature',
    type: 'number',
    min: 0,
    max: 1,
    help: '0 is deterministic; higher values transcribe more loosely.',
  },
  {
    path: 'models.asr.no_speech_threshold',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'No-speech threshold',
    type: 'number',
    min: 0,
    max: 1,
    help: 'Raise to discard more silent or noisy segments.',
  },
  {
    path: 'models.asr.logprob_threshold',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'Log-probability threshold',
    type: 'number',
    min: -10,
    max: 0,
    help: 'Segments the model is less confident about than this are dropped.',
  },
  {
    path: 'models.asr.min_duration_sec',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'Minimum segment duration (s)',
    type: 'number',
    min: 0,
    max: 10,
    help: 'Shorter segments are discarded as noise.',
  },
  {
    path: 'models.asr.min_words',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'Minimum words per segment',
    type: 'number',
    min: 0,
    max: 50,
    integer: true,
  },
  {
    path: 'models.asr.max_chars_per_segment',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrRecognition',
    label: 'Max characters per segment',
    type: 'number',
    min: 0,
    max: 2000,
    integer: true,
    help: '0 disables merging of transcript segments.',
  },
  {
    path: 'models.diarization.backend',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrDiarization',
    label: 'Diarization backend',
    type: 'enum',
    options: ['pyannote', 'campplus'],
    help: 'campplus pairs with the funasr / paraformer-zh provider.',
  },
  {
    path: 'models.diarization.global_speaker_similarity_threshold',
    file: CONFIG,
    group: 'asr',
    subgroup: 'asrDiarization',
    label: 'Speaker similarity threshold',
    type: 'number',
    min: 0,
    max: 1,
    help: 'Lower merges more voices into one speaker.',
  },

  // -------------------------------------------------------------------------
  // Audio processing
  // -------------------------------------------------------------------------
  {
    path: 'audio_preprocessing.chunking',
    file: CONFIG,
    group: 'audio',
    subgroup: 'audioChunking',
    label: 'Chunk audio before transcription',
    type: 'boolean',
    help: 'Off transcribes the whole recording in one pass (funasr / paraformer-zh only).',
  },
  {
    path: 'audio_preprocessing.chunk_duration_sec',
    file: CONFIG,
    group: 'audio',
    subgroup: 'audioChunking',
    label: 'Chunk duration (s)',
    type: 'number',
    min: 5,
    max: 600,
    integer: true,
  },
  {
    path: 'audio_preprocessing.silence_threshold',
    file: CONFIG,
    group: 'audio',
    subgroup: 'audioChunking',
    label: 'Silence threshold (dB)',
    type: 'number',
    min: -100,
    max: 0,
  },
  {
    path: 'audio_preprocessing.silence_duration',
    file: CONFIG,
    group: 'audio',
    subgroup: 'audioChunking',
    label: 'Minimum silence length (s)',
    type: 'number',
    min: 0.05,
    max: 10,
    help: 'How long a quiet stretch must last to count as a split point.',
  },
  {
    path: 'audio_preprocessing.search_window_sec',
    file: CONFIG,
    group: 'audio',
    subgroup: 'audioChunking',
    label: 'Silence search window (s)',
    type: 'number',
    min: 0,
    max: 30,
    help: 'How far past a chunk boundary to look for silence to cut on.',
  },
  {
    path: 'audio_util.max_size_mb',
    file: CONFIG,
    group: 'audio',
    subgroup: 'audioUploads',
    label: 'Max audio upload size (MB)',
    type: 'number',
    min: 1,
    max: 10240,
    integer: true,
  },
  {
    path: 'pipeline.delete_chunks_after_use',
    file: CONFIG,
    group: 'audio',
    subgroup: 'audioCleanup',
    label: 'Delete chunks after use',
    type: 'boolean',
  },

  // -------------------------------------------------------------------------
  // Summarization and topics
  // -------------------------------------------------------------------------
  {
    path: 'models.summarizer.mode',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'summarizer',
    label: 'Summarizer mode',
    type: 'enum',
    options: ['dialog', 'teacher', 'hybrid'],
  },
  {
    path: 'models.text_gen.chunking.enabled',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'promptChunking',
    label: 'Chunk long transcripts',
    type: 'boolean',
    help: 'Off summarizes the whole transcript in one pass.',
  },
  {
    path: 'models.text_gen.chunking.max_prompt_tokens',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'promptChunking',
    label: 'Max prompt tokens',
    type: 'autoNumber',
    min: 512,
    max: 262144,
    help: 'auto takes the smaller of the quality and memory ceilings; a number overrides both.',
  },
  {
    path: 'models.text_gen.chunking.max_content_tokens',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'promptChunking',
    label: 'Quality ceiling (tokens)',
    type: 'number',
    min: 0,
    max: 262144,
    integer: true,
    help: 'Largest prompt worth sending, regardless of free memory. 0 lifts the ceiling.',
  },
  {
    path: 'models.text_gen.chunking.gpu_memory_safety_margin',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'promptChunking',
    label: 'GPU memory safety margin',
    type: 'number',
    min: 0.1,
    max: 1,
    help: 'Fraction of free device memory the prompt may use. Lower it if summarization runs out of memory.',
  },
  {
    path: 'models.text_gen.chunking.map_max_new_tokens',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'promptChunking',
    label: 'Per-segment note length (tokens)',
    type: 'number',
    min: 64,
    max: 8192,
    integer: true,
  },
  {
    path: 'models.text_gen.segmentation.window_max_new_tokens',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'topicSegmentation',
    label: 'Topics per window (tokens)',
    type: 'number',
    min: 64,
    max: 8192,
    integer: true,
    help: 'Length cap for the topic list generated from each window.',
  },
  {
    path: 'models.text_gen.segmentation.topics_target',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'topicSegmentation',
    label: 'Target topic count',
    type: 'number',
    min: 1,
    max: 200,
    integer: true,
  },
  {
    path: 'models.text_gen.segmentation.topics_min',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'topicSegmentation',
    label: 'Minimum topic count',
    type: 'number',
    min: 1,
    max: 200,
    integer: true,
    help: 'Merging stops once the list is this short.',
  },
  {
    path: 'models.text_gen.segmentation.topics_max',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'topicSegmentation',
    label: 'Maximum topic count',
    type: 'number',
    min: 1,
    max: 200,
    integer: true,
  },
  {
    path: 'mindmap.min_token',
    file: CONFIG,
    group: 'summarization',
    subgroup: 'mindmap',
    label: 'Mind map minimum tokens',
    type: 'number',
    min: 1,
    max: 4096,
    integer: true,
    help: 'Transcript shorter than this produces no mind map.',
  },

  // -------------------------------------------------------------------------
  // Models and devices
  // -------------------------------------------------------------------------
  {
    path: 'models.text_gen.vlm_name',
    file: CONFIG,
    group: 'devices',
    subgroup: 'textGen',
    label: 'VLM model',
    type: 'string',
    maxLength: 200,
  },
  {
    path: 'models.text_gen.device',
    file: CONFIG,
    group: 'devices',
    subgroup: 'textGen',
    label: 'Text generation (VLM) device',
    type: 'enum',
    options: ['GPU', 'CPU', 'NPU'],
  },
  {
    path: 'models.text_gen.weight_format',
    file: CONFIG,
    group: 'devices',
    subgroup: 'textGen',
    label: 'VLM weight format',
    type: 'enum',
    options: ['int4', 'int8'],
  },
  {
    path: 'models.text_gen.max_new_tokens',
    file: CONFIG,
    group: 'devices',
    subgroup: 'textGen',
    label: 'VLM max new tokens',
    type: 'number',
    min: 64,
    max: 32768,
    integer: true,
  },
  {
    path: 'models.ocr.provider',
    file: CONFIG,
    group: 'devices',
    subgroup: 'ocr',
    label: 'OCR provider',
    type: 'enum',
    options: ['openvino', 'native'],
  },
  {
    path: 'models.ocr.device',
    file: CONFIG,
    group: 'devices',
    subgroup: 'ocr',
    label: 'OCR device',
    type: 'enum',
    options: ['CPU', 'GPU'],
  },

  // -------------------------------------------------------------------------
  // Video analytics
  // -------------------------------------------------------------------------
  {
    path: 'models.va.front_pose_model',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseModels',
    label: 'Front pose model',
    type: 'enum',
    options: ['yolov8m-pose', 'yolo11m-pose', 'yolo26m-pose'],
  },
  {
    path: 'models.va.back_pose_model',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseModels',
    label: 'Back pose model',
    type: 'enum',
    options: ['yolov8s-pose', 'yolo11s-pose', 'yolo26s-pose'],
  },
  {
    path: 'models.va.threshold',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseModels',
    label: 'Detection threshold',
    type: 'number',
    min: 0,
    max: 1,
    help: 'Confidence a YOLO detection needs to count.',
  },
  {
    path: 'va_pipeline.stream_protocol',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'streaming',
    label: 'Stream protocol',
    type: 'enum',
    options: ['webrtc', 'hls'],
  },
  {
    path: 'va_pipeline.rtsp_codec',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'streaming',
    label: 'Stream codec',
    type: 'enum',
    options: ['h264', 'h265'],
  },
  {
    path: 'va_pipeline.completion_timeout_sec',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'streaming',
    label: 'Pipeline timeout (s)',
    type: 'number',
    min: 60,
    max: 86400,
    integer: true,
    help: 'How long to wait for a video pipeline to finish before giving up.',
  },
  {
    path: 'va_pipeline.pose_statistics.min_frames_for_transition',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseStatistics',
    label: 'Frames to confirm a raised hand',
    type: 'number',
    min: 1,
    max: 300,
    integer: true,
    help: 'For identified students.',
  },
  {
    path: 'va_pipeline.pose_statistics.min_frames_for_transition_unid',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseStatistics',
    label: 'Frames to confirm a raised hand (unidentified)',
    type: 'number',
    min: 1,
    max: 300,
    integer: true,
  },
  {
    path: 'va_pipeline.pose_statistics.min_stand_frames',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseStatistics',
    label: 'Frames before counting a stand-up',
    type: 'number',
    min: 1,
    max: 300,
    integer: true,
  },
  {
    path: 'va_pipeline.pose_statistics.absence_threshold',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseStatistics',
    label: 'Forget a student after (frames)',
    type: 'number',
    min: 1,
    max: 3600,
    integer: true,
    help: 'Unseen for this many frames and the student is dropped (90 ≈ 3s).',
  },
  {
    path: 'va_pipeline.pose_statistics.center_dist_threshold',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseStatistics',
    label: 'Same-person distance threshold',
    type: 'number',
    min: 0,
    max: 1,
    help: 'How close two boxes must be to count as the same person.',
  },
  {
    path: 'va_pipeline.pose_statistics.unidentified_max',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseStatistics',
    label: 'Max unidentified students tracked',
    type: 'number',
    min: 1,
    max: 500,
    integer: true,
  },
  {
    path: 'va_pipeline.pose_statistics.stale_unidentified_threshold',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'poseStatistics',
    label: 'Forget an unidentified student after (frames)',
    type: 'number',
    min: 1,
    max: 3600,
    integer: true,
  },
  {
    path: 'board_ocr.frame_rate',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'boardOcr',
    label: 'Board OCR frame rate',
    type: 'string',
    maxLength: 16,
    pattern: /^\d+(\/\d+)?$/,
    patternHint: 'a frame rate such as 1 or 1/3',
    help: 'Frames per second, as a whole number or fraction.',
  },
  {
    path: 'board_ocr.debug',
    file: CONFIG,
    group: 'videoAnalytics',
    subgroup: 'boardOcr',
    label: 'Board OCR debug output',
    type: 'boolean',
  },

  // -------------------------------------------------------------------------
  // Content search
  // -------------------------------------------------------------------------
  {
    path: 'content_search.ocr_enabled',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csGeneral',
    label: 'Document OCR',
    type: 'boolean',
    wizard: true,
    help: 'Extract text from images inside uploaded documents.',
  },
  {
    path: 'content_search.video_summarization_enabled',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csGeneral',
    label: 'Video summarization',
    type: 'boolean',
  },
  {
    path: 'content_search.storage.document_max_mb',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csStorage',
    label: 'Max document size (MB)',
    type: 'number',
    min: 1,
    max: 10240,
    integer: true,
    wizard: true,
  },
  {
    path: 'content_search.storage.video_max_mb',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csStorage',
    label: 'Max video size (MB)',
    type: 'number',
    min: 1,
    max: 102400,
    integer: true,
    wizard: true,
  },
  {
    path: 'content_search.file_ingest.doc_embedding_device',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csIngest',
    label: 'Document embedding device',
    type: 'enum',
    options: ['CPU', 'GPU'],
  },
  {
    path: 'content_search.file_ingest.frame_extract_interval',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csIngest',
    label: 'Frame extraction interval',
    type: 'number',
    min: 1,
    max: 600,
    integer: true,
    help: 'Index one frame every N frames of an uploaded video.',
  },
  {
    path: 'content_search.file_ingest.frame_extract_interval_sparse',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csIngest',
    label: 'Frame extraction interval (long videos)',
    type: 'number',
    min: 1,
    max: 1800,
    integer: true,
    help: 'Used instead for videos over 20 minutes.',
  },
  {
    path: 'content_search.file_ingest.do_detect_and_crop',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csIngest',
    label: 'Detect and crop before embedding',
    type: 'boolean',
    help: 'Slower, but focuses the embedding on detected objects.',
  },
  {
    path: 'content_search.file_ingest.document_parser.chunk_method',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csParser',
    label: 'Document chunking',
    type: 'enum',
    options: ['semantic', 'fixed'],
    help: 'semantic splits by meaning; fixed splits by character count.',
  },
  {
    path: 'content_search.file_ingest.document_parser.chunk_size',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csParser',
    label: 'Chunk size (characters)',
    type: 'number',
    min: 50,
    max: 4000,
    integer: true,
    help: 'Fixed mode only.',
  },
  {
    path: 'content_search.file_ingest.document_parser.chunk_overlap',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csParser',
    label: 'Chunk overlap (characters)',
    type: 'number',
    min: 0,
    max: 2000,
    integer: true,
    help: 'Fixed mode only.',
  },
  {
    path: 'content_search.file_ingest.document_parser.semantic_min_chunk_size',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csParser',
    label: 'Minimum chunk size (characters)',
    type: 'number',
    min: 50,
    max: 4000,
    integer: true,
    help: 'Semantic mode only: shorter chunks are merged into the next one.',
  },
  {
    path: 'content_search.file_ingest.document_parser.semantic_breakpoint_percentile',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csParser',
    label: 'Breakpoint percentile',
    type: 'number',
    min: 0,
    max: 100,
    integer: true,
    help: 'Semantic mode only: higher gives fewer, larger chunks.',
  },
  {
    path: 'content_search.file_ingest.document_parser.semantic_buffer_size',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csParser',
    label: 'Sentence buffer size',
    type: 'number',
    min: 1,
    max: 10,
    integer: true,
    help: 'Semantic mode only: neighbouring sentences grouped when comparing similarity.',
  },
  {
    path: 'content_search.file_ingest.reranker.device',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csReranker',
    label: 'Reranker device',
    type: 'enum',
    options: ['GPU', 'CPU'],
  },
  {
    path: 'content_search.file_ingest.reranker.dedup_time_threshold',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csReranker',
    label: 'Frame dedup window (s)',
    type: 'number',
    min: 0,
    max: 120,
    help: 'Frames from one video closer together than this are merged.',
  },
  {
    path: 'content_search.file_ingest.reranker.overfetch_multiplier',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csReranker',
    label: 'Overfetch multiplier',
    type: 'number',
    min: 1,
    max: 20,
    integer: true,
    help: 'Retrieve this many times top_k candidates before reranking.',
  },
  {
    path: 'content_search.video_preprocess.chunk_duration_s',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csVideoPreprocess',
    label: 'Video chunk duration (s)',
    type: 'number',
    min: 5,
    max: 600,
    integer: true,
  },
  {
    path: 'content_search.video_preprocess.chunk_overlap_s',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csVideoPreprocess',
    label: 'Video chunk overlap (s)',
    type: 'number',
    min: 0,
    max: 120,
    integer: true,
  },
  {
    path: 'content_search.video_preprocess.max_num_frames',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csVideoPreprocess',
    label: 'Frames per chunk',
    type: 'number',
    min: 1,
    max: 64,
    integer: true,
    help: 'Frames sent to the VLM for each chunk.',
  },
  {
    path: 'content_search.video_preprocess.max_image_pixels',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csVideoPreprocess',
    label: 'Max frame area (pixels)',
    type: 'number',
    min: 65536,
    max: 16777216,
    integer: true,
    help: 'Larger frames are downscaled before being sent to the VLM.',
  },
  {
    path: 'content_search.video_preprocess.max_completion_tokens',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csVideoPreprocess',
    label: 'Max tokens per chunk summary',
    type: 'number',
    min: 64,
    max: 8192,
    integer: true,
  },
  {
    path: 'content_search.video_preprocess.vlm_timeout_seconds',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csVideoPreprocess',
    label: 'VLM timeout (s)',
    type: 'number',
    min: 30,
    max: 3600,
    integer: true,
  },
  {
    path: 'content_search.qa.max_context',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csQa',
    label: 'Answer context chunks',
    type: 'number',
    min: 1,
    max: 50,
    integer: true,
  },
  {
    path: 'content_search.qa.max_tokens',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csQa',
    label: 'Answer max tokens',
    type: 'number',
    min: 64,
    max: 32768,
    integer: true,
  },
  {
    path: 'content_search.qa.max_history_turns',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csQa',
    label: 'Conversation turns remembered',
    type: 'number',
    min: 0,
    max: 20,
    integer: true,
    help: 'Prior user/assistant pairs sent along with the question.',
  },
  {
    path: 'content_search.qa.context_window',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csQa',
    label: 'Context window (tokens)',
    type: 'number',
    min: 1024,
    max: 262144,
    integer: true,
    help: 'Token budget for dynamic context selection.',
  },
  {
    path: 'content_search.qa.retrieval_score_threshold',
    file: CONFIG,
    group: 'contentSearch',
    subgroup: 'csQa',
    label: 'Retrieval score threshold',
    type: 'number',
    min: 0,
    max: 100,
    integer: true,
    help: 'Minimum relevance (0-100) for a chunk to be used as context.',
  },

  // -------------------------------------------------------------------------
  // Report
  // -------------------------------------------------------------------------
  {
    path: 'report.max_keywords',
    file: CONFIG,
    group: 'report',
    label: 'Max keywords in report',
    type: 'number',
    min: 1,
    max: 50,
    integer: true,
  },
  {
    path: 'report.max_difficulty_points',
    file: CONFIG,
    group: 'report',
    label: 'Max difficulty points in report',
    type: 'number',
    min: 1,
    max: 20,
    integer: true,
  },
  {
    path: 'report.pacing_slow_max',
    file: CONFIG,
    group: 'report',
    label: 'Slow pacing up to (words/min)',
    type: 'number',
    min: 60,
    max: 1000,
    integer: true,
    help: 'Below this the lesson is reported as slow-paced.',
  },
  {
    path: 'report.pacing_fast_min',
    file: CONFIG,
    group: 'report',
    label: 'Fast pacing from (words/min)',
    type: 'number',
    min: 60,
    max: 2000,
    integer: true,
    help: 'Above this the lesson is reported as fast-paced.',
  },

  // -------------------------------------------------------------------------
  // Project (runtime_config.yaml) and proxy (.proxy-config)
  // -------------------------------------------------------------------------
  { path: 'Project.name', file: RUNTIME, group: 'project', label: 'Project name', type: 'string', maxLength: 128 },
  { path: 'Project.location', file: RUNTIME, group: 'project', label: 'Storage location', type: 'path' },
  {
    path: 'Project.microphone',
    file: RUNTIME,
    group: 'project',
    label: 'Microphone',
    type: 'string',
    maxLength: 256,
    help: 'Leave empty to use the system default.',
  },

  { path: 'httpProxy', file: PROXY, group: 'proxy', label: 'HTTP_PROXY', type: 'url', maxLength: 512, wizard: true },
  { path: 'httpsProxy', file: PROXY, group: 'proxy', label: 'HTTPS_PROXY', type: 'url', maxLength: 512, wizard: true },
  {
    path: 'noProxy',
    file: PROXY,
    group: 'proxy',
    label: 'NO_PROXY',
    type: 'string',
    maxLength: 512,
    wizard: true,
    help: 'Comma-separated hosts that bypass the proxy.',
  },
];

const BY_PATH = new Map(FIELDS.map((field) => [`${field.file}:${field.path}`, field]));

function get(file, path) {
  return BY_PATH.get(`${file}:${path}`);
}

// Returns the value to write, or throws with a message safe to show the user.
function coerce(field, value) {
  switch (field.type) {
    case 'boolean':
      if (typeof value !== 'boolean') throw new Error(`${field.label} must be true or false.`);
      return value;

    case 'enum':
      if (!field.options.includes(value)) throw new Error(`${field.label} must be one of: ${field.options.join(', ')}.`);
      return value;

    case 'number': {
      const numeric = typeof value === 'number' ? value : Number(value);
      if (!Number.isFinite(numeric)) throw new Error(`${field.label} must be a number.`);
      if (field.integer && !Number.isInteger(numeric)) throw new Error(`${field.label} must be a whole number.`);
      if (field.min !== undefined && numeric < field.min) throw new Error(`${field.label} must be at least ${field.min}.`);
      if (field.max !== undefined && numeric > field.max) throw new Error(`${field.label} must be at most ${field.max}.`);
      return numeric;
    }

    // "auto" or a whole number. Written as a real YAML integer, not a quoted
    // string, so the file keeps reading the way it was hand-written.
    case 'autoNumber': {
      const text = String(value).trim();
      if (text.toLowerCase() === 'auto') return 'auto';
      if (!/^\d+$/.test(text)) throw new Error(`${field.label} must be "auto" or a whole number.`);
      const numeric = Number(text);
      if (field.min !== undefined && numeric < field.min) throw new Error(`${field.label} must be at least ${field.min}.`);
      if (field.max !== undefined && numeric > field.max) throw new Error(`${field.label} must be at most ${field.max}.`);
      return numeric;
    }

    case 'url': {
      if (typeof value !== 'string') throw new Error(`${field.label} must be text.`);
      const trimmed = value.trim();
      if (!trimmed) return '';
      if (!/^https?:\/\/[^\s"']+$/.test(trimmed)) throw new Error(`${field.label} must be an http(s) URL.`);
      if (trimmed.length > field.maxLength) throw new Error(`${field.label} is too long.`);
      return trimmed;
    }

    case 'path':
    case 'string':
    case 'secret': {
      if (typeof value !== 'string') throw new Error(`${field.label} must be text.`);
      // Control characters would corrupt the YAML document or the .env-style
      // consumers downstream.
      if (/[\u0000-\u001f\u007f]/.test(value)) throw new Error(`${field.label} contains invalid characters.`);
      if (value.length > (field.maxLength ?? 512)) throw new Error(`${field.label} is too long.`);
      if (field.pattern && !field.pattern.test(value)) {
        throw new Error(`${field.label} must be ${field.patternHint ?? 'in the expected format'}.`);
      }
      return value;
    }

    default:
      throw new Error(`Unsupported field type for ${field.path}.`);
  }
}

module.exports = { FIELDS, GROUPS, SUBGROUPS, CONFIG, RUNTIME, PROXY, get, coerce };
