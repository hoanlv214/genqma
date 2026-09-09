export class SessionTaskPool {
  private readonly tasks = new Map<string, Promise<void>>();

  constructor(readonly maxConcurrency: number) {
    if (!Number.isInteger(maxConcurrency) || maxConcurrency < 1) {
      throw new Error("maxConcurrency must be a positive integer");
    }
  }

  get activeCount(): number {
    return this.tasks.size;
  }

  get availableSlots(): number {
    return Math.max(0, this.maxConcurrency - this.activeCount);
  }

  get isFull(): boolean {
    return this.activeCount >= this.maxConcurrency;
  }

  has(sessionId: string): boolean {
    return this.tasks.has(sessionId);
  }

  tryStart(sessionId: string, run: () => Promise<void>): boolean {
    if (this.isFull || this.tasks.has(sessionId)) {
      return false;
    }

    // Schedule on the next microtask so the task is registered before it can
    // complete, reject, or attempt to free its slot.
    const task = Promise.resolve().then(run);
    this.tasks.set(sessionId, task);

    void task
      .finally(() => {
        if (this.tasks.get(sessionId) === task) {
          this.tasks.delete(sessionId);
        }
      })
      .catch(() => {
        // The caller owns task error handling. This catch only prevents the
        // bookkeeping promise returned by finally() from being unhandled.
      });

    return true;
  }

  async waitForCapacity(timeoutMs: number): Promise<void> {
    if (!this.isFull) return;

    let timeoutId: NodeJS.Timeout | undefined;
    const timeout = new Promise<void>((resolve) => {
      timeoutId = setTimeout(resolve, timeoutMs);
    });
    const completions = [...this.tasks.values()].map((task) => task.catch(() => undefined));
    try {
      await Promise.race([timeout, ...completions]);
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
    }
  }
}
