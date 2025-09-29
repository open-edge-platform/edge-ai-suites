export type StreamEvent =
  | { type: 'transcript'; token: string }
  | { type: 'summary_token'; token: string }
  | { type: 'error'; message: string }
  | { type: 'done' };

export interface StreamOptions {
  tokenDelayMs?: number;
  startDelayMs?: number; 
  signal?: AbortSignal;
  onSessionId?: (id: string | null) => void; 
  alreadyTokenized?: boolean; 
};

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

function tokenize(text: string): string[] {
  // keep trailing whitespace for natural typewriter effect
  return Array.from(text.matchAll(/\S+\s*/g)).map((m) => m[0]);
}

export async function* simulateTranscriptStream(
  chunks: string[],
  opts: StreamOptions = {}
): AsyncGenerator<StreamEvent> {
  const delay = opts.tokenDelayMs ?? 22;
  const startDelay = opts.startDelayMs ?? 0;
  if (startDelay > 0) await sleep(startDelay);
  for (const line of chunks) {
    if (opts.alreadyTokenized) {
      if (opts.signal?.aborted) return;
      yield { type: 'transcript', token: line };
      await sleep(delay);
    } else {
      for (const tok of tokenize(line + ' ')) {
        if (opts.signal?.aborted) return;
        yield { type: 'transcript', token: tok };
        await sleep(delay);
      }
    }
  }
  yield { type: 'done' };
}

export async function* simulateSummaryStream(
  text: string,
  opts: StreamOptions = {}
): AsyncGenerator<StreamEvent> {
  const delay = opts.tokenDelayMs ?? 38;
  const startDelay = opts.startDelayMs ?? 0;
  if (startDelay > 0) await sleep(startDelay);
  if (opts.alreadyTokenized) {
    for (const tok of text.split(' ')) {
      if (opts.signal?.aborted) return;
      yield { type: 'summary_token', token: tok + ' ' };
      await sleep(delay);
    }
  } else {
    for (const tok of tokenize(text)) {
      if (opts.signal?.aborted) return;
      yield { type: 'summary_token', token: tok };
      await sleep(delay);
    }
  }
  yield { type: 'done' };
}