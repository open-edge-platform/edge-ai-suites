export async function* typewriterStream(
    text: string,
    delayMs: number = 30,
    signal?: AbortSignal
  ): AsyncGenerator<string> {
    // Split into words, keeping trailing whitespace for natural effect
    const tokens = Array.from(text.matchAll(/\S+\s*/g)).map(m => m[0]);
    for (const token of tokens) {
      if (signal?.aborted) return;
      yield token;
      await new Promise(res => setTimeout(res, delayMs));
    }
  }