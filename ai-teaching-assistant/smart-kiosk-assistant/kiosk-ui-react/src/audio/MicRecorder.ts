import { encodeWav } from "./wav";

// Captures microphone audio at a fixed sample rate, exposes an AnalyserNode for
// live visualization, and emits WAV chunks (~chunkSeconds each) via a callback.
export class MicRecorder {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private buffer: Float32Array[] = [];
  private buffered = 0;
  private chunkSamples: number;

  public analyser: AnalyserNode | null = null;

  constructor(
    private sampleRate: number,
    chunkSeconds: number,
    private onChunk: (wav: ArrayBuffer) => void
  ) {
    this.chunkSamples = Math.floor(sampleRate * chunkSeconds);
  }

  async start(deviceId?: string): Promise<void> {
    this.ctx = new AudioContext({ sampleRate: this.sampleRate });
    // Some browsers ignore the requested sampleRate; use the actual one.
    const actualRate = this.ctx.sampleRate;

    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: deviceId ? { exact: deviceId } : undefined,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    });

    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.source.connect(this.analyser);

    this.processor = this.ctx.createScriptProcessor(4096, 1, 1);
    this.source.connect(this.processor);
    // Route through a muted gain node so onaudioprocess fires without echo.
    const mute = this.ctx.createGain();
    mute.gain.value = 0;
    this.processor.connect(mute);
    mute.connect(this.ctx.destination);

    this.processor.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      this.buffer.push(new Float32Array(input));
      this.buffered += input.length;
      if (this.buffered >= this.chunkSamples) {
        this.flush(actualRate);
      }
    };
  }

  private flush(rate: number): void {
    if (this.buffered === 0) return;
    const merged = new Float32Array(this.buffered);
    let offset = 0;
    for (const b of this.buffer) {
      merged.set(b, offset);
      offset += b.length;
    }
    this.buffer = [];
    this.buffered = 0;
    this.onChunk(encodeWav(merged, rate));
  }

  async stop(): Promise<void> {
    const rate = this.ctx?.sampleRate ?? this.sampleRate;
    if (this.processor) {
      this.processor.onaudioprocess = null;
      this.flush(rate); // send trailing audio
      this.processor.disconnect();
    }
    this.source?.disconnect();
    this.analyser?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    if (this.ctx && this.ctx.state !== "closed") await this.ctx.close();
    this.ctx = null;
    this.analyser = null;
  }
}
