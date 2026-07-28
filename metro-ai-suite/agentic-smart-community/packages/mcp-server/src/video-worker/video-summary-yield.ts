/**
 * Video summary service load check — ensures the service has capacity before dispatching.
 * Prevents overloading the model with concurrent requests.
 */
export class VideoSummaryYield {
  private maxConcurrent: number;
  private active = 0;

  constructor(maxConcurrent: number = 2) {
    this.maxConcurrent = maxConcurrent;
  }

  async acquire(): Promise<void> {
    while (this.active >= this.maxConcurrent) {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
    this.active++;
  }

  release(): void {
    this.active = Math.max(0, this.active - 1);
  }

  get currentLoad(): number {
    return this.active;
  }
}
