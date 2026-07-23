/**
 * Unified HTTP client for the multilevel-video-understanding service. Both
 * video-worker (task-poller — runs VLM on a clip) and generate-report
 * (LLM-only over an SRT timeline) go through this class.
 *
 * Server contract: docs/apis/multilevel-video-understanding (also browsable at
 * GET /v1/openapi.json on the running service). Field names mirror the
 * server's SummarizationRequest exactly.
 */

/** Mirrors multilevel's SUMMARIZATION_METHOD_TYPE enum values. */
export type SummaryMethod = "SIMPLE" | "USE_VLM_T-1" | "USE_LLM_T-1" | "USE_ALL_T-1";

/** Mirrors multilevel's `processor_kwargs`. */
export interface ProcessorKwargs {
  /** Sampling rate. Set to 0 to skip frame extraction (caption-only mode). */
  process_fps?: number;
  /** Total hierarchical levels. */
  levels?: number;
  /** Group size per level, must align with `levels`. `-1` means single group. */
  level_sizes?: number[];
  /** Chunking algorithm. Default `pelt` (scene-switch); `uniform` slices by 15 s. */
  chunking_method?: "pelt" | "uniform";
}

/** Inline SRT subtitle payload formats accepted by the service. */
export type SubtitlePayload =
  | { url: string }
  | { text: string }
  | { b64gzip: string };

export interface SummaryUsage {
  prompt_tokens?: number;
  image_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
}

export interface SummaryResponse {
  /** "completed" | "failed" — see SummarizationStatus enum on the service side. */
  status: string;
  /** The summary text; non-null when status="completed". */
  summary: string | null;
  message?: string;
  job_id?: string;
  video_name?: string;
  video_duration?: number;
  usage?: SummaryUsage;
}

/** Path map: video paths starting with `hostPrefix` are rewritten to `containerPrefix`. */
export interface PathRemap {
  hostPrefix: string;
  containerPrefix: string;
}

/** Video-file mode — task-poller summarises a recorded clip. */
export interface VideoSummarizeRequest {
  /** Local path or http(s)/file:// URL. Subject to path_remap before POST. */
  video: string;
  task?: string;
  prompt?: string;
  method?: SummaryMethod;
  processor_kwargs?: ProcessorKwargs;
  video_subtitles?: SubtitlePayload;
}

/** Caption-only mode — generate-report aggregates an SRT timeline (no video). */
export interface SubtitleSummarizeRequest {
  /** SRT text built from DB rows. */
  srtText: string;
  task: string;
  prompt?: string;
  method?: SummaryMethod;
  /** Overrides — defaults to {process_fps: 0, levels, level_sizes} computed by caller. */
  processor_kwargs?: ProcessorKwargs;
}

/** Default request timeout. Caption-only over long SRT can take minutes. */
const DEFAULT_TIMEOUT_MS = 600_000;

/** Strip `<think>...</think>` blocks some LLMs prefix the response with. */
function stripThinkTags(text: string): string {
  return text.replace(/<think>[\s\S]*?<\/think>\s*/g, "").trim();
}

export class VideoSummaryClient {
  private baseUrl: string;
  private pathRemap?: PathRemap;
  private timeoutMs: number;

  constructor(baseUrl: string, pathRemap?: PathRemap, timeoutMs: number = DEFAULT_TIMEOUT_MS) {
    this.baseUrl = baseUrl;
    this.pathRemap = pathRemap;
    this.timeoutMs = timeoutMs;
  }

  private remapVideoPath(path: string): string {
    if (!this.pathRemap) return path;
    const { hostPrefix, containerPrefix } = this.pathRemap;
    if (path.startsWith(hostPrefix)) {
      return containerPrefix + path.slice(hostPrefix.length);
    }
    return path;
  }

  /**
   * POST the assembled payload to /v1/summary, raise on HTTP / status failure,
   * and strip any `<think>` prologue from the returned summary. Shared by both
   * video-file mode and caption-only mode.
   */
  private async post(payload: Record<string, unknown>): Promise<SummaryResponse> {
    const response = await fetch(`${this.baseUrl}/v1/summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(this.timeoutMs),
    });

    if (!response.ok) {
      // FastAPI returns structured `detail` on 4xx/5xx — surface it to caller logs.
      let detail: string;
      try { detail = JSON.stringify(await response.json()); }
      catch { detail = response.statusText; }
      throw new Error(`video-summary HTTP ${response.status}: ${detail.slice(0, 500)}`);
    }

    const body = (await response.json()) as SummaryResponse;
    if (body.status !== "completed") {
      throw new Error(`video-summary status=${body.status}: ${body.message ?? "<no message>"}`);
    }
    if (body.summary) body.summary = stripThinkTags(body.summary);
    return body;
  }

  /** Video-file mode: send a clip path; service runs the full VLM→LLM pipeline. */
  async summarize(req: VideoSummarizeRequest): Promise<SummaryResponse> {
    return this.post({
      ...req,
      video: this.remapVideoPath(req.video),
      method: req.method ?? "USE_ALL_T-1",
    });
  }

  /**
   * Caption-only mode: send an SRT timeline as inline text; service runs LLM
   * aggregation only (no frame extraction). Caller is responsible for computing
   * `processor_kwargs.levels` / `level_sizes` since chunking is text-based.
   */
  async summarizeSubtitles(req: SubtitleSummarizeRequest): Promise<SummaryResponse> {
    return this.post({
      video: "none",
      video_subtitles: { text: req.srtText },
      task: req.task,
      prompt: req.prompt,
      method: req.method ?? "USE_ALL_T-1",
      processor_kwargs: { process_fps: 0, ...(req.processor_kwargs ?? {}) },
    });
  }
}
