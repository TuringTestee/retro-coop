// Local automated experiment: no coordinator, ROM transfer, public route, or user microphone.
"use strict";
const percentile = (xs, p) => {
  if (!xs.length) return 0;
  const sorted = [...xs].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))];
};
window.probe = {};
probe.init = async ({ rom64, wasm64, role, identity, seconds = 600 }) => {
  const initial = performance.now(),
    stats = {
      role,
      seconds,
      hashes: [],
      identity,
      rttMs: [],
      copyMs: [],
      paintMs: [],
      emulateMs: [],
      transferMs: [],
      voiceLevels: [],
      voiceFrequencyHz: [],
      sent: 0,
      maxBuffered: 0,
      maxRemoteInputs: 0,
      stalls: 0,
      errors: [],
    };
  probe.initial = initial;
  probe.stats = stats;
  probe.role = role;
  probe.frame = 0;
  probe.limit = Math.ceil(seconds * 60.0988);
  probe.ready = false;
  probe.remote = new Map();
  probe.local = new Map();
  probe.pending = new Set();
  probe.epoch = 0;
  probe.busy = false;
  probe.audioSent = 0;
  probe.audioQueued = 0;
  stats.audioBackpressurePolls = 0;
  stats.voiceMissedSlots = 0;
  probe.finished = false;
  probe.audio = new AudioContext({
    sampleRate: 48000,
    latencyHint: "interactive",
  });
  // Mute this page only; keep the measured audio graph running upstream.
  probe.output = probe.audio.createGain();
  probe.output.gain.value = 0;
  probe.outputMeter = probe.audio.createAnalyser();
  probe.output.connect(probe.outputMeter).connect(probe.audio.destination);
  const sound = document.querySelector("#sound");
  sound.checked = false;
  sound.onchange = () => {
    probe.output.gain.setValueAtTime(sound.checked ? 1 : 0, probe.audio.currentTime);
  };
  await probe.audio.audioWorklet.addModule("/realtime-audio.js");
  probe.sink = new AudioWorkletNode(probe.audio, "bounded-audio", {
    numberOfInputs: 0,
    outputChannelCount: [1],
  });
  probe.sink.connect(probe.output);
  probe.sink.port.onmessage = ({ data: d }) => {
    if (d.kind === "queued" && d.epoch === probe.epoch) {
      // Account for messages still in transit; never assume those samples drained.
      probe.audioQueued = d.queued + (probe.audioSent - d.received);
    }
    if (d.kind === "stats") {
      stats.audio = d;
      probe.audioStatsResolve?.();
    }
    if (d.kind === "flushed") {
      stats.flush = d;
      probe.flushResolve?.(d);
    }
  };
  document.querySelector("#enable").onclick = async () => {
    stats.audioEnableAtMs = performance.now() - initial;
    await probe.audio.resume();
    stats.audioRunningAtMs = performance.now() - initial;
  };
  const voice = probe.audio.createOscillator(),
    gain = probe.audio.createGain(),
    dest = probe.audio.createMediaStreamDestination();
  voice.frequency.value = role === 0 ? 523 : 659;
  gain.gain.value = 0.05;
  voice.connect(gain).connect(dest);
  voice.start();
  probe.voice = voice;
  probe.voiceTrack = dest.stream.getAudioTracks()[0];
  probe.pc = new RTCPeerConnection({ iceServers: [] });
  probe.pc.addTrack(probe.voiceTrack, dest.stream);
  probe.pc.ontrack = ({ streams }) => {
    probe.remoteStream = streams[0];
    probe.remoteElement = document.createElement("audio");
    probe.remoteElement.srcObject = streams[0];
    document.body.append(probe.remoteElement);
    probe.remoteElement.volume = 0;
    probe.remoteVoice = probe.audio.createMediaStreamSource(streams[0]);
    probe.remoteElement
      .play()
      .then(() => {
        stats.remotePlaybackStartedAtMs = performance.now() - initial;
      })
      .catch((error) => stats.errors.push("Remote playback: " + String(error)));
    probe.analyser = probe.audio.createAnalyser();
    probe.analyser.fftSize = 1024;
    probe.remoteVoice.connect(probe.analyser);
    probe.analyser.connect(probe.output);
    stats.trackAtMs = performance.now() - initial;
    probe.voicePoll = setInterval(() => {
      const a = new Float32Array(1024);
      probe.analyser.getFloatTimeDomainData(a);
      const rms = Math.sqrt(a.reduce((s, v) => s + v * v, 0) / a.length);
      if (rms > 0.001 && !stats.voiceFirstEnergyAtMs) {
        stats.voiceFirstEnergyAtMs = performance.now() - initial;
        stats.voiceEnableToEnergyMs =
          stats.voiceFirstEnergyAtMs - stats.audioEnableAtMs;
      }
    }, 20);
  };
  probe.pc.onconnectionstatechange = () => {
    if (probe.pc.connectionState === "failed")
      stats.errors.push("WebRTC failed");
  };
  const receive = (d) => {
    if (d.kind === "hello") {
      if (d.identity !== identity) {
        stats.errors.push("Fingerprint mismatch");
        probe.pc.close();
      } else {
        stats.identityMatched = true;
        probe.ready = true;
      }
    } else if (d.kind === "input") {
      if (
        !Number.isInteger(d.frame) ||
        d.frame < probe.frame ||
        d.frame > probe.frame + 120 ||
        !Number.isInteger(d.mask) ||
        d.mask < 0 ||
        d.mask > 255
      ) {
        stats.errors.push("Invalid input range");
        return;
      }
      if (probe.remote.has(d.frame)) {
        stats.errors.push("Duplicate input");
        return;
      }
      probe.remote.set(d.frame, d.mask);
      stats.maxRemoteInputs = Math.max(
        stats.maxRemoteInputs,
        probe.remote.size,
      );
    } else if (d.kind === "ping")
      probe.send({ kind: "pong", started: d.started });
    else if (d.kind === "pong") stats.rttMs.push(performance.now() - d.started);
    else if (d.kind === "hash") {
      if (
        !Number.isInteger(d.frame) ||
        d.frame < 1 ||
        d.frame > probe.limit ||
        (d.frame % 600 !== 0 && d.frame !== probe.limit) ||
        typeof d.hash !== "string" ||
        !/^[0-9a-f]{64}$/.test(d.hash)
      ) {
        stats.errors.push("Invalid hash envelope");
        return;
      }
      (probe.peerHashes ??= new Map()).set(d.frame, d.hash);
      const own = stats.hashes.find((x) => x.frame === d.frame);
      if (own && own.hash !== d.hash)
        stats.errors.push("Canonical divergence at " + d.frame);
    }
  };
  const wire = (channel) => {
    probe.channel = channel;
    channel.onopen = () => {
      stats.channelOpenMs = performance.now() - initial;
      channel.send(JSON.stringify({ kind: "hello", identity }));
    };
    channel.onmessage = (event) => {
      if (typeof event.data !== "string" || event.data.length > 512) {
        stats.errors.push("Input envelope too large");
        return;
      }
      try {
        receive(JSON.parse(event.data));
      } catch (e) {
        stats.errors.push(String(e));
      }
    };
  };
  if (role === 0)
    wire(probe.pc.createDataChannel("d02-inputs", { ordered: true }));
  else probe.pc.ondatachannel = (event) => wire(event.channel);
  // Actual packet delay/loss is applied by the isolated namespace's kernel qdisc.
  probe.send = (message) => {
    const encoded = JSON.stringify(message);
    if (encoded.length > 512) throw Error("Bounded envelope exhausted");
    if (probe.channel.readyState !== "open")
      throw Error("Closed input channel");
    stats.maxBuffered = Math.max(
      stats.maxBuffered,
      probe.channel.bufferedAmount,
    );
    if (probe.channel.bufferedAmount > 65536)
      throw Error("Channel backpressure cap");
    probe.channel.send(encoded);
    stats.sent++;
  };
  probe.worker = new Worker("/realtime-worker.js");
  await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(Error("Worker initialization timeout")),
      30000,
    );
    probe.worker.onmessage = ({ data: d }) => {
      clearTimeout(timer);
      if (d.kind === "error") reject(Error(d.error));
      else {
        Object.assign(stats, d);
        resolve();
      }
    };
    probe.worker.postMessage({ kind: "init", rom64, wasm64 });
  });
  stats.localReadyMs = performance.now() - initial;
  stats.audioSampleRate = probe.audio.sampleRate;
  probe.worker.onmessage = ({ data: d }) => {
    if (d.kind === "error") {
      stats.errors.push(d.error);
      probe.busy = false;
      return;
    }
    if (d.kind === "epoch") {
      stats.coreQueueEmpty = d.empty;
      probe.busy = false;
      return;
    }
    if (d.kind !== "frame") return;
    probe.busy = false;
    probe.frame = d.frame + 1;
    stats.emulateMs.push(d.emulateMs);
    stats.copyMs.push(d.copyMs);
    stats.transferMs.push(
      performance.timeOrigin + performance.now() - d.sentAt,
    );
    const sampleCount = d.audio.byteLength / 4;
    if (sampleCount > 2048) {
      stats.errors.push("Unexpected per-frame PCM bound");
      return;
    }
    probe.audioSent += sampleCount;
    probe.audioQueued += sampleCount;
    probe.sink.port.postMessage(
      {
        kind: "samples",
        epoch: probe.epoch,
        samples: new Float32Array(d.audio),
      },
      [d.audio],
    );
    // Consume the transferred video on the main thread, without painting a product UI.
    stats.videoBytes = (stats.videoBytes ?? 0) + d.video.byteLength;
    const paint = performance.now();
    document
      .querySelector("canvas")
      .getContext("2d")
      .putImageData(
        new ImageData(new Uint8ClampedArray(d.video), 256, 240),
        0,
        0,
      );
    stats.paintMs.push(performance.now() - paint);
    if (d.canonical) {
      stats.hashes.push({ frame: probe.frame, hash: d.canonical });
      probe.send({ kind: "hash", frame: probe.frame, hash: d.canonical });
      if (
        probe.peerHashes?.has(probe.frame) &&
        probe.peerHashes.get(probe.frame) !== d.canonical
      )
        stats.errors.push("Canonical divergence at " + probe.frame);
    }
    if (!stats.firstFrameMs) {
      stats.firstFrameMs = performance.now() - initial;
      stats.startToFirstFrameMs = performance.now() - probe.started;
    }
  };
  probe.localMask = (frame) => {
    let mask = 0;
    for (let i = 0; i < 8; i++)
      if (Math.floor((frame + role * 37) / (11 + i * 7)) % 2) mask |= 1 << i;
    return mask;
  };
  return { localReadyMs: stats.localReadyMs };
};
probe.description = async (type) => {
  probe.stats.localDescriptionAtMs = performance.now() - probe.initial;
  await probe.pc.setLocalDescription(
    type === "offer"
      ? await probe.pc.createOffer()
      : await probe.pc.createAnswer(),
  );
  if (probe.pc.iceGatheringState !== "complete")
    await new Promise((resolve, reject) => {
      const timer = setTimeout(
        () => reject(Error("ICE gathering timeout")),
        15000,
      );
      probe.pc.addEventListener("icegatheringstatechange", () => {
        if (probe.pc.iceGatheringState === "complete") {
          clearTimeout(timer);
          resolve();
        }
      });
    });
  return probe.pc.localDescription.toJSON();
};
probe.start = async () => {
  if (!probe.ready || probe.audio.state !== "running")
    throw Error("Peer/audio not ready");
  probe.sink.port.postMessage({ kind: "begin" });
  probe.started = performance.now();
  probe.stats.startAtMs = probe.started - probe.initial;
  let nextInput = 0,
    nextPing = 0,
    lastVoice = 0,
    epochDone = false;
  const schedule = () => {
    if (probe.finished) return;
    try {
      const elapsed = performance.now() - probe.started;
      if (elapsed > (probe.stats.seconds + 120) * 1000) {
        probe.stats.errors.push("Realtime deadline");
        probe.finished = true;
        return;
      }
      while (nextInput < Math.min(probe.frame + 13, probe.limit)) {
        const mask = nextInput < 12 ? 0 : probe.localMask(nextInput - 12);
        probe.local.set(nextInput, mask);
        probe.send({ kind: "input", frame: nextInput, mask });
        nextInput++;
      }
      if (elapsed >= nextPing) {
        probe.send({ kind: "ping", started: performance.now() });
        nextPing += 1000;
      }
      if (elapsed - lastVoice >= 1000 && probe.analyser) {
        const a = new Float32Array(1024);
        probe.analyser.getFloatTimeDomainData(a);
        const rms = Math.sqrt(a.reduce((s, v) => s + v * v, 0) / a.length);
        probe.stats.voiceLevels.push(rms);
        let crossings = 0;
        for (let i = 1; i < a.length; i++)
          if (a[i - 1] < 0 && a[i] >= 0) crossings++;
        probe.stats.voiceFrequencyHz.push((crossings * 48000) / a.length);
        const slot = Math.floor(elapsed / 1000) * 1000;
        probe.stats.voiceMissedSlots += Math.max(0, (slot - lastVoice) / 1000 - 1);
        lastVoice = slot;
      }
      const target = Math.min(
        probe.limit,
        Math.floor((Math.max(0, elapsed - 150) * 60.0988) / 1000),
      );
      if (probe.audioQueued > 8000) probe.stats.audioBackpressurePolls++;
      if (!probe.busy && probe.frame < target && probe.audioQueued <= 8000) {
        if (!probe.remote.has(probe.frame)) probe.stats.stalls++;
        else {
          // One scripted common frame boundary restores the same local snapshot in each peer.
          if (!epochDone && probe.frame === Math.floor(probe.limit / 2)) {
            epochDone = true;
            probe.epoch++;
            probe.busy = true;
            probe.sink.port.postMessage({ kind: "flush", epoch: probe.epoch });
            probe.worker.postMessage({ kind: "epoch" });
          } else {
            const local = probe.local.get(probe.frame),
              remote = probe.remote.get(probe.frame);
            probe.local.delete(probe.frame);
            probe.remote.delete(probe.frame);
            probe.busy = true;
            probe.worker.postMessage({
              kind: "step",
              frame: probe.frame,
              one: probe.role === 0 ? local : remote,
              two: probe.role === 0 ? remote : local,
              hash:
                (probe.frame + 1) % 600 === 0 ||
                probe.frame + 1 === probe.limit,
            });
          }
        }
      }
      if (
        probe.frame === probe.limit &&
        elapsed >= probe.stats.seconds * 1000
      ) {
        probe.completedAt = elapsed;
        probe.sink.port.postMessage({ kind: "stop" });
        return;
      }
      probe.timer = setTimeout(schedule, 2);
    } catch (error) {
      probe.stats.errors.push(String(error));
      probe.finished = true;
    }
  };
  schedule();
  return true;
};
probe.result = async () => {
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(Error("Audio stats deadline")), 2000);
    probe.audioStatsResolve = () => {
      clearTimeout(timer);
      resolve();
    };
    probe.sink.port.postMessage({ kind: "stats" });
  });
  const rtc = [];
  const all = await probe.pc.getStats();
  const selected = new Set(
    [...all.values()]
      .filter((s) => s.type === "transport")
      .map((s) => s.selectedCandidatePairId)
      .filter(Boolean),
  );
  for (const s of all.values()) {
    if (s.type === "media-source" && s.kind === "audio")
      rtc.push({
        type: s.type,
        audioLevel: s.audioLevel,
        totalAudioEnergy: s.totalAudioEnergy,
        totalSamplesDuration: s.totalSamplesDuration,
      });
    if (s.type === "outbound-rtp" && s.kind === "audio")
      rtc.push({
        type: s.type,
        packetsSent: s.packetsSent,
        bytesSent: s.bytesSent,
      });
    if (s.type === "inbound-rtp" && s.kind === "audio")
      rtc.push({
        type: s.type,
        kind: s.kind,
        packetsReceived: s.packetsReceived,
        packetsLost: s.packetsLost,
        jitter: s.jitter,
        totalAudioEnergy: s.totalAudioEnergy,
        totalSamplesReceived: s.totalSamplesReceived,
      });
    if (
      s.type === "candidate-pair" &&
      (selected.has(s.id) || (s.state === "succeeded" && s.nominated))
    ) {
      const local = all.get(s.localCandidateId),
        remote = all.get(s.remoteCandidateId);
      rtc.push({
        type: s.type,
        state: s.state,
        selected: selected.has(s.id),
        nominated: s.nominated,
        currentRoundTripTime: s.currentRoundTripTime,
        bytesSent: s.bytesSent,
        bytesReceived: s.bytesReceived,
        local: {
          address: local?.address,
          protocol: local?.protocol,
          candidateType: local?.candidateType,
        },
        remote: {
          address: remote?.address,
          protocol: remote?.protocol,
          candidateType: remote?.candidateType,
        },
      });
    }
  }
  const voiceTrack = {
    local: probe.voiceTrack.readyState,
    remote: probe.remoteStream?.getAudioTracks().map((t) => ({
      enabled: t.enabled,
      muted: t.muted,
      readyState: t.readyState,
    })),
  };
  const stats = probe.stats;
  const outputSamples = new Float32Array(probe.outputMeter.fftSize);
  probe.outputMeter.getFloatTimeDomainData(outputSamples);
  const summary = (xs) => ({
    count: xs.length,
    p50: percentile(xs, 0.5),
    p95: percentile(xs, 0.95),
    max: xs.length ? xs.reduce((a, b) => Math.max(a, b), 0) : 0,
  });
  return {
    ...stats,
    frames: probe.frame,
    wallMs: probe.completedAt ?? performance.now() - probe.started,
    rtc,
    voiceTrack,
    iceSelection: [...all.values()]
      .filter((s) => s.type === "transport" || s.type === "candidate-pair")
      .map((s) => ({
        type: s.type,
        id: s.id,
        state: s.state,
        nominated: s.nominated,
        selectedCandidatePairId: s.selectedCandidatePairId,
        bytesSent: s.bytesSent,
        bytesReceived: s.bytesReceived,
      })),
    outputMuted: probe.output.gain.value === 0,
    outputPeak: outputSamples.reduce(
      (peak, sample) => Math.max(peak, Math.abs(sample)), 0,
    ),
    emulateMs: summary(stats.emulateMs),
    copyMs: summary(stats.copyMs),
    paintMs: summary(stats.paintMs),
    transferMs: summary(stats.transferMs),
    rttMs: summary(stats.rttMs),
    voiceLevels: summary(stats.voiceLevels),
    voiceFrequencyHz: summary(stats.voiceFrequencyHz),
    peerHashesMatched: stats.hashes.every(
      (x) => probe.peerHashes?.get(x.frame) === x.hash,
    ),
    pendingInputs: probe.pending.size,
    remoteInputQueue: probe.remote.size,
  };
};

probe.close = async () => {
  probe.finished = true;
  clearTimeout(probe.timer);
  clearInterval(probe.voicePoll);
  probe.worker.terminate();
  probe.voice.stop();
  probe.voiceTrack.stop();
  probe.remoteStream?.getTracks().forEach((t) => t.stop());
  probe.remoteElement?.pause();
  if (probe.remoteElement) probe.remoteElement.srcObject = null;
  probe.pc.close();
  await probe.audio.close();
  return {
    localTrack: probe.voiceTrack.readyState,
    connection: probe.pc.connectionState,
    audio: probe.audio.state,
    remoteElementPaused: probe.remoteElement?.paused,
  };
};
