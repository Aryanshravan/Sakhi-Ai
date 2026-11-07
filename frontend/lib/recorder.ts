const TARGET_SAMPLE_RATE = 16000;

// Voice activity detection: stop when the child has spoken and then gone quiet.
const SPEECH_LEVEL = 0.02; // RMS above this counts as speech
const SILENCE_MS = 1400; // quiet this long after speech ends the recording
const NO_SPEECH_MS = 8000; // give up if nothing is said for this long
const MAX_MS = 20000;
const MIN_MANUAL_MS = 700; // a manual stop before this is treated as an accidental tap
const CHECK_EVERY_MS = 100;

export type RecordingResult = { kind: "speech"; wav: Blob } | { kind: "no-speech" };

export interface Recording {
  /** Settles when recording ends: silence after speech, a manual stop(), the time limit, or cancel(). */
  result: Promise<RecordingResult>;
  /** Stop now and keep what was recorded. */
  stop: () => void;
  /** Stop now and throw the recording away. */
  cancel: () => void;
}

export async function startRecording(): Promise<Recording> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true },
  });
  const context = new AudioContext();
  await context.resume();
  const analyser = context.createAnalyser();
  analyser.fftSize = 1024;
  context.createMediaStreamSource(stream).connect(analyser);

  const recorder = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  recorder.ondataavailable = (event) => chunks.push(event.data);
  recorder.start();

  const startedAt = performance.now();
  const samples = new Float32Array(analyser.fftSize);
  let heardSpeech = false;
  let lastLoudAt = startedAt;
  let ended = false;
  let resolveResult: (result: RecordingResult) => void;
  let rejectResult: (reason: unknown) => void;
  const result = new Promise<RecordingResult>((resolve, reject) => {
    resolveResult = resolve;
    rejectResult = reject;
  });

  function end(keep: boolean) {
    if (ended) return;
    ended = true;
    clearInterval(timer);
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop());
      void context.close();
      if (!keep) return resolveResult({ kind: "no-speech" });
      toWav(new Blob(chunks)).then((wav) => resolveResult({ kind: "speech", wav }), rejectResult);
    };
    recorder.stop();
  }

  const timer = setInterval(() => {
    analyser.getFloatTimeDomainData(samples);
    const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
    const now = performance.now();
    if (rms > SPEECH_LEVEL) {
      heardSpeech = true;
      lastLoudAt = now;
    }
    if (heardSpeech && now - lastLoudAt > SILENCE_MS) end(true);
    else if (!heardSpeech && now - startedAt > NO_SPEECH_MS) end(false);
    else if (now - startedAt > MAX_MS) end(heardSpeech);
  }, CHECK_EVERY_MS);

  return {
    result,
    stop: () => end(heardSpeech || performance.now() - startedAt >= MIN_MANUAL_MS),
    cancel: () => end(false),
  };
}

// Browsers record WebM/Opus, but the speech service wants WAV, so convert here.
async function toWav(recording: Blob): Promise<Blob> {
  const context = new AudioContext();
  const decoded = await context.decodeAudioData(await recording.arrayBuffer());
  await context.close();

  const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * TARGET_SAMPLE_RATE), TARGET_SAMPLE_RATE);
  const source = offline.createBufferSource();
  source.buffer = decoded;
  source.connect(offline.destination);
  source.start();
  const rendered = await offline.startRendering();
  return encodeWav(rendered.getChannelData(0), TARGET_SAMPLE_RATE);
}

function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const writeText = (offset: number, text: string) =>
    [...text].forEach((char, i) => view.setUint8(offset + i, char.charCodeAt(0)));

  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeText(8, "WAVEfmt ");
  view.setUint32(16, 16, true); // PCM header size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // bits per sample
  writeText(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return new Blob([view], { type: "audio/wav" });
}
