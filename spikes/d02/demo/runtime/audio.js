// Shared bounded PCM scheduler from the playable D02 demo. Each caller owns its context.
export function createAudioQueue(getContext, isEnabled, getDestination = () => getContext().destination) {
  let nextAudio = 0;
  const sources = new Set();
  function flush() {
    for (const source of sources) { try { source.stop(); } catch {} }
    sources.clear(); nextAudio = 0;
  }
  function play(buffer) {
    const context = getContext();
    if (!isEnabled() || context?.state !== 'running') return;
    const samples = new Float32Array(buffer);
    if (!samples.length) return;
    if (nextAudio < context.currentTime || nextAudio > context.currentTime + .15) {
      flush(); nextAudio = context.currentTime + .035;
    }
    const data = context.createBuffer(1, samples.length, 48000);
    data.copyToChannel(samples, 0);
    const source = context.createBufferSource(); source.buffer = data;
    source.connect(getDestination()); sources.add(source);
    source.onended = () => sources.delete(source);
    source.start(nextAudio); nextAudio += data.duration;
  }
  return { play, flush };
}
