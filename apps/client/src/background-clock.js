// The audio rendering thread keeps a clock while a game tab is hidden and
// window timers are throttled. Output buffers remain silent.
class RetroCoopClock extends AudioWorkletProcessor {
 constructor() {super();this.frames=0;}
 process(_inputs,outputs) {
  this.frames+=(outputs[0]?.[0]?.length ?? 128);
  if(this.frames>=sampleRate/60){this.frames%=sampleRate/60;this.port.postMessage(0);}
  return true;
 }
}
registerProcessor('retro-coop-background-clock',RetroCoopClock);
