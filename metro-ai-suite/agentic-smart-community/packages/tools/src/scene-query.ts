import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

/** Resize image so longest edge <= maxEdge. Uses ffmpeg (no extra deps). Returns JPEG buffer. */
function resizeFrame(inputPath: string, maxEdge: number): Buffer {
  const tmpOut = inputPath + ".resized.jpg";
  try {

    try {
      execFileSync("ffmpeg", [
        "-y", "-i", inputPath,
        "-vf", `scale='if(gt(iw,ih),${maxEdge},-2)':'if(gt(iw,ih),-2,${maxEdge})'`,
        "-frames:v", "1",
        "-q:v", "2",
        tmpOut,
      ], { timeout: 10_000, stdio: "pipe" });
    } catch (err: any) {
      if (err.code === "ENOENT") {
        throw new Error("ffmpeg not found — install it first (e.g. apt install ffmpeg / brew install ffmpeg)");
      }
      throw err;
    }
    return fs.readFileSync(tmpOut);
  } finally {
    try { fs.unlinkSync(tmpOut); } catch { /* non-fatal */ }
  }
}

export interface SceneQueryParams {
  monitor_id: string;
  vlm_url: string; // vllm-serving-ipex base URL, e.g. http://localhost:41091/v1
  prompt?: string;
  model?: string;
  max_edge_px?: number;
  data_dir?: string; // directory containing latest.jpg and queries/
}

const FALLBACK_PROMPT =
  "Describe the key elements in this scene in 1-2 sentences: what objects or subjects are present, their location and state, any notable activity or risk factors. If the frame is empty or has no content reply 'empty frame'.";

export async function sceneQuery(params: SceneQueryParams): Promise<unknown> {
  if (!params.data_dir) {
    throw new Error("data_dir is required — set to the monitor's data directory containing latest.jpg");
  }

  const framePath = path.join(params.data_dir, "latest.jpg");
  if (!fs.existsSync(framePath)) {
    throw new Error(`No latest.jpg at ${framePath} — stream may not be running`);
  }

  // Resize: longest edge <= maxEdge using ffmpeg scale filter (no extra deps)
  const maxEdge = params.max_edge_px ?? 720;
  const frameBuffer = resizeFrame(framePath, maxEdge);

  // Archive query frame (best-effort, failures are silently ignored)
  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const queryDir = path.join(params.data_dir, "queries", ts.slice(0, 10));
  try {
    fs.mkdirSync(queryDir, { recursive: true });
    fs.writeFileSync(path.join(queryDir, `scene_${ts.slice(11)}.jpg`), frameBuffer);
  } catch { /* best-effort */ }

  const vlmUrl = params.vlm_url;
  const model = params.model ?? "default";
  const effectivePrompt = params.prompt ?? FALLBACK_PROMPT;
  const base64 = frameBuffer.toString("base64");

  const payload = {
    model,
    messages: [
      {
        role: "user",
        content: [
          { type: "image_url", image_url: { url: `data:image/jpeg;base64,${base64}` } },
          { type: "text", text: effectivePrompt },
        ],
      },
    ],
    max_tokens: 512,
    chat_template_kwargs: { enable_thinking: false },
  };

  const resp = await fetch(`${vlmUrl}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(120_000),
  });

  if (!resp.ok) {
    const errText = await resp.text().catch(() => "");
    throw new Error(`VLM error ${resp.status}: ${errText.slice(0, 200)}`);
  }

  const result = (await resp.json()) as {
    choices?: Array<{ message?: { content?: string } }>;
  };
  let content = result.choices?.[0]?.message?.content ?? "(no content)";
  // Strip <think>...</think> blocks from Qwen3-style responses
  content = content.replace(/<think>[\s\S]*?<\/think>\s*/g, "").trim();

  return { scene: content };
}
