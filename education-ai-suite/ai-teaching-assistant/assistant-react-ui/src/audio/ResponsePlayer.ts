// Plays a queue of response-audio WAV URLs sequentially, routing playback
// through an AnalyserNode so the response can be visualized in real time.
export class ResponsePlayer {
  private ctx: AudioContext;
  public analyser: AnalyserNode;
  private queue: string[] = [];
  private playing = false;
  private current: AudioBufferSourceNode | null = null;

  public onStart?: () => void;
  public onIdle?: () => void;

  constructor() {
    this.ctx = new AudioContext();
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.analyser.connect(this.ctx.destination);
  }

  enqueue(url: string): void {
    this.queue.push(url);
    if (!this.playing) void this.drain();
  }

  private async drain(): Promise<void> {
    this.playing = true;
    if (this.ctx.state === "suspended") await this.ctx.resume();
    this.onStart?.();
    while (this.queue.length > 0) {
      const url = this.queue.shift()!;
      try {
        await this.playOne(url);
      } catch (err) {
        // Skip a failed segment but keep the queue moving.
        console.warn("response playback failed", err);
      }
    }
    this.playing = false;
    this.onIdle?.();
  }

  private async playOne(url: string): Promise<void> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`fetch audio failed: HTTP ${res.status}`);
    const arrayBuffer = await res.arrayBuffer();
    const audioBuffer = await this.ctx.decodeAudioData(arrayBuffer);
    await new Promise<void>((resolve) => {
      const src = this.ctx.createBufferSource();
      src.buffer = audioBuffer;
      src.connect(this.analyser);
      src.onended = () => resolve();
      this.current = src;
      src.start();
    });
    this.current = null;
  }

  // Immediately stop playback and drop any queued segments. The player stays
  // usable — subsequent enqueue() calls will start a fresh drain loop.
  stop(): void {
    this.queue = [];
    if (this.current) {
      try {
        this.current.onended = null;
        this.current.stop();
      } catch {
        // Already stopped/ended — ignore.
      }
      this.current = null;
    }
    this.playing = false;
    this.onIdle?.();
  }

  get isPlaying(): boolean {
    return this.playing;
  }

  async close(): Promise<void> {
    this.queue = [];
    if (this.ctx.state !== "closed") await this.ctx.close();
  }
}
