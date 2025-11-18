export async function* typewriterStream(
  text: string,
  delayMs: number,
  signal?: AbortSignal
) {
  const parts = text.split(/(\s+)/);
 
  for (const part of parts) {
    if (signal?.aborted) break;
    yield part;
    if (part.trim().length > 0 && delayMs > 0) {
      await new Promise((res) => setTimeout(res, delayMs));
    }
  }
}