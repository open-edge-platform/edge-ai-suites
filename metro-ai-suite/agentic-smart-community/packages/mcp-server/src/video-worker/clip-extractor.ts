import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

/**
 * Fallback clip extraction using ffmpeg.
 * Used when videostream-analytics doesn't provide pre-segmented clips.
 */
export class ClipExtractor {
  async extract(
    sourceUrl: string,
    outputPath: string,
    durationSec: number = 10,
  ): Promise<string> {
    await execFileAsync("ffmpeg", [
      "-i", sourceUrl,
      "-t", String(durationSec),
      "-c", "copy",
      "-y",
      outputPath,
    ]);
    return outputPath;
  }
}
