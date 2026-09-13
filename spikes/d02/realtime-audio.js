// Fixed 250 ms capacity. Missing samples become silence; overflow fails the probe.
class BoundedAudio extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ring = new Float32Array(12000);
    this.read = 0;
    this.size = 0;
    this.epoch = 0;
    this.fade = 0;
    this.ticks = 0;
    this.stats = {
      received: 0,
      played: 0,
      underrun: 0,
      overflow: 0,
      maxQueued: 0,
      stale: 0,
      flushes: 0,
      flushed: 0,
      energy: 0,
    };
    this.port.onmessage = ({ data: d }) => {
      if (d.kind === "begin") {
        this.frozen = null;
        for (const key of Object.keys(this.stats)) this.stats[key] = 0;
      }
      if (d.kind === "flush") {
        this.stats.flushed += this.size;
        this.size = 0;
        this.read = 0;
        this.epoch = d.epoch;
        this.fade = 240;
        this.stats.flushes++;
        this.port.postMessage({
          kind: "flushed",
          epoch: this.epoch,
          queued: this.size,
        });
      }
      if (d.kind === "samples") {
        if (d.epoch !== this.epoch) {
          this.stats.stale += d.samples.length;
          return;
        }
        this.stats.received += d.samples.length;
        for (const value of d.samples) {
          if (this.size === this.ring.length) {
            this.stats.overflow++;
            continue;
          }
          this.ring[(this.read + this.size) % this.ring.length] = value;
          this.size++;
        }
        this.stats.maxQueued = Math.max(this.stats.maxQueued, this.size);
        this.reportQueue();
      }
      if (d.kind === "stop")
        this.frozen = {
          ...this.stats,
          queued: this.size,
          epoch: this.epoch,
          capacity: this.ring.length,
        };
      if (d.kind === "stats" || d.kind === "stop")
        this.port.postMessage({
          kind: "stats",
          ...(this.frozen ?? {
            ...this.stats,
            queued: this.size,
            epoch: this.epoch,
            capacity: this.ring.length,
          }),
        });
    };
  }
  reportQueue() {
    this.port.postMessage({
      kind: "queued",
      epoch: this.epoch,
      queued: this.size,
      received: this.stats.received,
    });
  }
  process(inputs, outputs) {
    const out = outputs[0][0];
    for (let i = 0; i < out.length; i++) {
      let value = 0;
      if (this.size) {
        value = this.ring[this.read];
        this.read = (this.read + 1) % this.ring.length;
        this.size--;
        this.stats.played++;
        if (this.fade) {
          value *= 1 - this.fade / 240;
          this.fade--;
        }
      } else this.stats.underrun++;
      out[i] = value;
      this.stats.energy += value * value;
    }
    if (++this.ticks % 16 === 0) this.reportQueue();
    return true;
  }
}
registerProcessor("bounded-audio", BoundedAudio);
