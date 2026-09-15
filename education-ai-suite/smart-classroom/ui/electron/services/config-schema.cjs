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
// runtime_config.yaml is excluded outright, which is why no field names it. Its
// `Project` block (name / location / microphone) is owned by the backend's
// `POST /project`: `<location>/<name>` prefixes both the session output tree and
// the SQLite path utils/session_store.py derives, so editing it here would move
// the store out from under recorded history. The microphone is picked from
// enumerated devices in the Start recording dialog instead of typed as text.
//
// A field belongs to a GROUP, which is the feature a user would go looking
// under, and to a SUBGROUP, which names the exact config.yaml node it lives in.
// Subgroups are what keep the two structures honest: if a field's path does not
// start with its subgroup's node, one of the two is wrong.
//
// Field labels are intentionally plain English rather than i18n keys: they name
// technical config paths, and the path itself is shown next to each control.

const CONFIG = 'config'; // config.yaml
const PROXY = 'proxy'; // .proxy-config (JSON)

// The features in config.yaml's `features:` block, in the order their toggles
// render.
//
// `dependsOn` mirrors `depends_on` in model_manager/features/*_feature.py.
// features/resolver.py walks that graph at startup and silently enables anything
// a live feature needs, so a toggle left off here is not necessarily off at run
// time — which is what the featureDependencies rule below reports. Label and
// graph share one table so the two cannot drift from each other, and
// tests/unit/test_feature_dependencies.py parses this table out of this file and
// fails if it drifts from the Python.
const FEATURES = {
  asr: { label: 'Speech recognition', dependsOn: [] },
  summary: { label: 'Summary', dependsOn: ['asr'] },
  mindmap: { label: 'Mind map', dependsOn: ['summary'] },
  topic_segmentation: { label: 'Topic segmentation', dependsOn: ['asr', 'content_search'] },
  video_analytics: { label: 'Video analytics', dependsOn: [] },
  board_ocr: { label: 'Board OCR', dependsOn: ['video_analytics'] },
  content_search: { label: 'Content search', dependsOn: [] },
  qa: { label: 'Question answering', dependsOn: ['content_search'] },
  grading: { label: 'Grading', dependsOn: [] },
  report: { label: 'Report', dependsOn: ['summary', 'mindmap', 'topic_segmentation', 'video_analytics'] },
};

const featurePath = (id) => `features.${id}.enabled`;

// The "Get started" screen shows `wizard: true` only; the full editor still
// shows everything.
const featureFields = Object.entries(FEATURES).map(([id, { label }]) => ({
  path: featurePath(id),
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
  { id: 'proxy', label: 'Proxy' },
];

// `node` is the config.yaml path the subgroup mirrors, shown under the heading.
// Order here is the order the sections render in. Groups whose fields all come
// from one node (features, report, proxy) have no subgroup at all.
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
    help: 'Required only when diarization is enabled and diarization model is not downloaded yet.',
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
    suggestions: ['Qwen/Qwen3-VL-8B-Instruct', 'Qwen/Qwen3.5-9B', 'Qwen/Qwen3.6-35B-A3B'],
    help: 'These options are downloaded as pre-converted OpenVINO IR; anything else is converted on first run.',
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
  // Proxy (.proxy-config)
  // -------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Cross-field rules
// ---------------------------------------------------------------------------
// coerce() sees one field at a time, so it cannot catch combinations that are
// each legal alone and broken together. Every rule below mirrors a check the
// Python side already makes when it loads the config; the point is to fail in
// the settings screen rather than minutes later in a backend traceback.
//
// A rule reads the config.yaml that saving *would* produce, so it sees pending
// edits and untouched on-disk values alike. `context` carries the few facts the
// document cannot answer on its own.

// components/asr/asr_handle.py::_build_processor dispatches on the provider
// paired with a substring of the model name.
const ASR_MODEL_FAMILY = { openai: 'whisper', openvino: 'whisper', funasr: 'paraformer' };

// utils/pipeline_modes.py: FunASR runs long audio natively and the CAM++
// speaker model is Mandarin-tuned, so both features demand this exact pair.
const FUNASR_PARAFORMER = 'ASR provider "funasr" with model "paraformer-zh"';

const lower = (value) => String(value ?? '').trim().toLowerCase();

// config.yaml uses YAML 1.1 booleans ("True"/"False") in places.
const asBool = (value) => (typeof value === 'boolean' ? value : lower(value) === 'true');

const isSet = (value) => {
  const text = lower(value);
  return text !== '' && text !== 'none' && text !== 'null';
};

function isFunasrParaformer(cfg) {
  return lower(cfg?.models?.asr?.provider) === 'funasr' && lower(cfg?.models?.asr?.name) === 'paraformer-zh';
}

/** "a", "a and b", "a, b and c" — messages below list two to six features. */
function listOf(labels) {
  if (labels.length < 3) return labels.join(' and ');
  return `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]}`;
}

const labelsOf = (ids) => listOf(ids.map((id) => FEATURES[id].label));

/**
 * Which features config.yaml switches on, read the way
 * model_manager/feature_bootstrap.py::_feature_flags reads it: `{enabled: bool}`
 * or a bare bool, and an id the file never mentions is off, because it never
 * reaches the resolver's `enabled` set.
 *
 * Null when there is no `features:` block at all — resolver.py treats that as
 * "enable everything" for backward compatibility, so it is not an all-off config.
 */
function enabledFeatures(cfg) {
  const block = cfg?.features;
  if (!block || typeof block !== 'object') return null;
  return Object.keys(FEATURES).filter((id) => {
    const spec = block[id];
    if (spec === undefined || spec === null) return false;
    if (typeof spec === 'object') return asBool(spec.enabled ?? true);
    return asBool(spec);
  });
}

/**
 * Every feature `id` needs, however deep. `seen` doubles as the cycle guard: the
 * table should be acyclic and resolver.py raises if it is not, but a rule must
 * never be the reason the settings screen hangs.
 */
function dependencyClosure(id, seen = new Set()) {
  for (const dep of FEATURES[id]?.dependsOn ?? []) {
    if (seen.has(dep)) continue;
    seen.add(dep);
    dependencyClosure(dep, seen);
  }
  return seen;
}

const RULES = [
  {
    id: 'asrProviderModel',
    summary: 'Provider and model do not match',
    file: CONFIG,
    // Both halves are flagged: either one is a reasonable thing to fix.
    paths: ['models.asr.provider', 'models.asr.name'],
    check(cfg) {
      const provider = lower(cfg?.models?.asr?.provider);
      const name = lower(cfg?.models?.asr?.name);
      const family = ASR_MODEL_FAMILY[provider];
      // An unknown provider is the enum's problem, and an empty name is caught
      // by the field itself; neither is this rule's to report.
      if (!family || !name) return null;
      if (name.includes(family)) return null;
      return `The ${provider} provider only runs ${family} models, but the ASR model is "${cfg.models.asr.name}". Pick a ${family} model or change the provider.`;
    },
  },
  {
    id: 'diarizationToken',
    summary: 'Needs a Hugging Face token',
    file: CONFIG,
    paths: ['models.asr.diarization', 'models.asr.hf_token'],
    check(cfg, context) {
      if (!asBool(cfg?.models?.asr?.diarization)) return null;
      // A token is only needed for the download. Once the model is on disk the
      // backend never asks for one again.
      if (context.diarizationModelReady) return null;
      if (isSet(cfg?.models?.asr?.hf_token)) return null;
      const model = cfg?.models?.diarization?.name || 'the diarization model';
      return `Speaker diarization needs ${model}, which is not downloaded yet, and downloading it needs a Hugging Face token. Add the token or turn diarization off.`;
    },
  },
  {
    id: 'campplusBackend',
    summary: 'Needs funasr / paraformer-zh',
    file: CONFIG,
    paths: ['models.diarization.backend'],
    check(cfg) {
      if (lower(cfg?.models?.diarization?.backend) !== 'campplus') return null;
      if (isFunasrParaformer(cfg)) return null;
      return `The campplus diarization backend requires ${FUNASR_PARAFORMER}, but the ASR is ${cfg?.models?.asr?.provider}/${cfg?.models?.asr?.name}.`;
    },
  },
  {
    id: 'wholeFileChunking',
    summary: 'Needs funasr / paraformer-zh',
    file: CONFIG,
    paths: ['audio_preprocessing.chunking'],
    check(cfg) {
      const chunking = cfg?.audio_preprocessing?.chunking;
      // Absent means the default, which is on; only an explicit false applies.
      if (chunking === undefined || chunking === null || asBool(chunking)) return null;
      if (isFunasrParaformer(cfg)) return null;
      return `Transcribing without chunking requires ${FUNASR_PARAFORMER}, but the ASR is ${cfg?.models?.asr?.provider}/${cfg?.models?.asr?.name}.`;
    },
  },
  {
    id: 'featuresNoneEnabled',
    summary: 'Nothing is enabled',
    file: CONFIG,
    // Any one of the ten is the fix, so all ten are offered — the same reasoning
    // asrProviderModel uses for flagging both halves of its pair.
    paths: Object.keys(FEATURES).map(featurePath),
    check(cfg) {
      const enabled = enabledFeatures(cfg);
      // No `features:` block means "enable everything", not "enable nothing".
      if (enabled === null || enabled.length) return null;
      // model_manager/feature_bootstrap.py::startup raises NO_FEATURES_MESSAGE.
      return 'No features are enabled, so the backend refuses to start. Turn on at least one.';
    },
  },
  {
    id: 'featureDependencies',
    // Only a warning: the backend runs this config perfectly well, it just runs
    // more than the file says. Blocking the save would be the settings screen
    // inventing a restriction the backend does not have, and config.yaml is
    // hand-editable, so a file that already trips this would strand the user.
    severity: 'warning',
    file: CONFIG,
    paths: [],
    check(cfg) {
      const enabled = enabledFeatures(cfg);
      if (!enabled?.length) return null;

      const explicit = new Set(enabled);
      // Missing feature id -> the enabled features that drag it back in.
      const requiredBy = new Map();
      for (const id of enabled) {
        for (const dep of dependencyClosure(id)) {
          if (explicit.has(dep)) continue;
          if (!requiredBy.has(dep)) requiredBy.set(dep, new Set());
          requiredBy.get(dep).add(id);
        }
      }
      if (!requiredBy.size) return null;

      // Table order throughout, so the message, the chips and the fix all name
      // the features in the order their toggles appear.
      const order = Object.keys(FEATURES);
      const missing = order.filter((id) => requiredBy.has(id));
      const drivers = order.filter((id) => [...requiredBy.values()].some((set) => set.has(id)));
      const them = missing.length > 1 ? 'them' : 'it';

      return {
        message:
          `${labelsOf(missing)} ${missing.length > 1 ? 'are' : 'is'} switched off, but ` +
          `${labelsOf(drivers)} need${drivers.length > 1 ? '' : 's'} ${them}, so the backend ` +
          `turns ${them} on at startup. Turn ${them} on here to match what actually runs, ` +
          `or switch ${labelsOf(drivers)} off.`,
        // Opposite ends of one rule, so the chips have to differ: one toggle is
        // being overridden, the other is what overrides it.
        paths: [
          ...missing.map((id) => ({ path: featurePath(id), summary: 'Turned on anyway' })),
          ...drivers.map((id) => ({ path: featurePath(id), summary: 'Needs features that are off' })),
        ],
        fix: missing.map((id) => ({ file: CONFIG, path: featurePath(id), value: true })),
      };
    },
  },
];

/**
 * `message` states the whole problem and is shown once; `summary` is the short
 * form for the field rows, which would otherwise repeat the sentence once per
 * field the rule names.
 *
 * A `check` returns null, that message as a string, or — when the fields it
 * flags are only known at check time — an object:
 *
 *   {
 *     message,            // required
 *     summary,            // overrides the rule's, for the whole finding
 *     paths,              // string, or {path, summary} to vary the chip per field
 *     fix,                // changes that would clear it, offered as one click
 *   }
 *
 * `advisory` marks a rule the backend tolerates: reported, never blocking. See
 * config-store.cjs::problemsFor, which is what acts on it.
 *
 * @param {object} cfg the config.yaml that saving would produce
 * @param {{diarizationModelReady?: boolean}} context facts the document cannot answer
 * @returns {Array<{file: string, path: string, rule: string, summary: string, message: string,
 *                  advisory: boolean, fix?: Array<{file: string, path: string, value: unknown}>}>}
 */
function validate(cfg, context = {}) {
  const problems = [];
  for (const rule of RULES) {
    let found = null;
    try {
      found = rule.check(cfg, context);
    } catch {
      // A rule must never be the reason a save fails; a malformed document is
      // the parser's business, not this one's.
      found = null;
    }
    if (!found) continue;

    const detail = typeof found === 'string' ? {} : found;
    const message = typeof found === 'string' ? found : found.message;
    if (!message) continue;

    for (const entry of detail.paths ?? rule.paths) {
      const path = typeof entry === 'string' ? entry : entry.path;
      problems.push({
        file: rule.file,
        path,
        rule: rule.id,
        summary: (typeof entry === 'string' ? null : entry.summary) ?? detail.summary ?? rule.summary,
        message,
        advisory: rule.severity === 'warning',
        ...(detail.fix ? { fix: detail.fix } : {}),
      });
    }
  }
  return problems;
}

module.exports = { FEATURES, FIELDS, GROUPS, SUBGROUPS, RULES, CONFIG, PROXY, get, coerce, validate };
