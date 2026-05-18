// Prosody analyser: extracts pitch contour and pause boundaries from a live
// MediaStream during recording, then returns a summary that the backend uses
// to restore punctuation and to comment on intonation.
//
// Pitch detection uses autocorrelation on a 2048-sample window — good enough
// for a coarse mean / range estimate, not a research-grade tracker. Pauses
// are detected from RMS energy with a fixed threshold and a minimum duration
// of 0.25 s (so micro-gaps between words don't count).

const FFT_SIZE = 2048;
const SILENCE_RMS = 0.015;
const MIN_PAUSE_SEC = 0.25;
const LONG_PAUSE_SEC = 0.7;
const PITCH_MIN_HZ = 70;
const PITCH_MAX_HZ = 400;
const VOICED_RMS = 0.02;

export class ProsodyAnalyser {
  constructor() {
    this.audioCtx = null;
    this.source = null;
    this.analyser = null;
    this.buf = null;
    this.startedAt = 0;
    this.samples = [];
    this.pauses = [];
    this._silenceStart = null;
    this._timer = null;
  }

  static isSupported() {
    return !!(window.AudioContext || window.webkitAudioContext);
  }

  async start(stream) {
    if (!ProsodyAnalyser.isSupported()) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.audioCtx = new Ctx();
    this.source = this.audioCtx.createMediaStreamSource(stream);
    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = FFT_SIZE;
    this.source.connect(this.analyser);
    this.buf = new Float32Array(this.analyser.fftSize);
    this.samples = [];
    this.pauses = [];
    this._silenceStart = null;
    this.startedAt = performance.now();
    this._timer = setInterval(() => this._tick(), 50);
  }

  _tick() {
    if (!this.analyser) return;
    this.analyser.getFloatTimeDomainData(this.buf);
    let sumSq = 0;
    for (let i = 0; i < this.buf.length; i++) sumSq += this.buf[i] * this.buf[i];
    const rms = Math.sqrt(sumSq / this.buf.length);
    const t = (performance.now() - this.startedAt) / 1000;

    let pitchHz = 0;
    if (rms > VOICED_RMS) {
      pitchHz = this._autocorrelate(this.buf, this.audioCtx.sampleRate);
    }
    this.samples.push({ t, rms, pitch_hz: pitchHz });

    if (rms < SILENCE_RMS) {
      if (this._silenceStart === null) this._silenceStart = t;
    } else if (this._silenceStart !== null) {
      const dur = t - this._silenceStart;
      if (dur >= MIN_PAUSE_SEC) {
        this.pauses.push([this._silenceStart, t]);
      }
      this._silenceStart = null;
    }
  }

  // Simple autocorrelation pitch detector. Searches lags corresponding to
  // 70-400 Hz and returns the lag with the highest correlation peak past
  // the first descent from lag=0. Returns 0 if no clear peak.
  _autocorrelate(buf, sampleRate) {
    const minLag = Math.floor(sampleRate / PITCH_MAX_HZ);
    const maxLag = Math.floor(sampleRate / PITCH_MIN_HZ);
    const n = buf.length;
    let bestLag = -1;
    let bestCorr = 0;
    let prev = 0;
    let descending = false;
    for (let lag = minLag; lag <= maxLag; lag++) {
      let corr = 0;
      const limit = n - lag;
      for (let i = 0; i < limit; i++) corr += buf[i] * buf[i + lag];
      if (lag === minLag) { prev = corr; continue; }
      if (!descending && corr < prev) descending = true;
      if (descending && corr > prev && corr > bestCorr) {
        bestCorr = corr;
        bestLag = lag;
      }
      prev = corr;
    }
    if (bestLag <= 0) return 0;
    const hz = sampleRate / bestLag;
    if (hz < PITCH_MIN_HZ || hz > PITCH_MAX_HZ) return 0;
    return hz;
  }

  async stop() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
    if (this._silenceStart !== null) {
      const t = (performance.now() - this.startedAt) / 1000;
      if (t - this._silenceStart >= MIN_PAUSE_SEC) {
        this.pauses.push([this._silenceStart, t]);
      }
      this._silenceStart = null;
    }
    try { if (this.source) this.source.disconnect(); } catch (e) { /* */ }
    try { if (this.analyser) this.analyser.disconnect(); } catch (e) { /* */ }
    try { if (this.audioCtx) await this.audioCtx.close(); } catch (e) { /* */ }
    this.audioCtx = null;
    this.source = null;
    this.analyser = null;
    return this.summary();
  }

  summary() {
    const total = this.samples.length;
    if (total === 0) return null;
    const pitches = this.samples.map((s) => s.pitch_hz).filter((p) => p > 0);
    const voicedRatio = pitches.length / total;
    let pitchMean = 0;
    let pitchStd = 0;
    let p10 = 0;
    let p90 = 0;
    if (pitches.length > 0) {
      pitchMean = pitches.reduce((a, b) => a + b, 0) / pitches.length;
      const variance = pitches.reduce((a, b) => a + (b - pitchMean) ** 2, 0) / pitches.length;
      pitchStd = Math.sqrt(variance);
      const sorted = pitches.slice().sort((a, b) => a - b);
      p10 = sorted[Math.floor(sorted.length * 0.1)] || 0;
      p90 = sorted[Math.floor(sorted.length * 0.9)] || sorted[sorted.length - 1] || 0;
    }
    const totalPause = this.pauses.reduce((s, [a, b]) => s + (b - a), 0);
    const longPauses = this.pauses.filter(([a, b]) => b - a >= LONG_PAUSE_SEC);
    return {
      pitch_mean_hz: +pitchMean.toFixed(1),
      pitch_p10_hz: +p10.toFixed(1),
      pitch_p90_hz: +p90.toFixed(1),
      pitch_range_hz: +(p90 - p10).toFixed(1),
      pitch_std_hz: +pitchStd.toFixed(1),
      voiced_ratio: +voicedRatio.toFixed(2),
      pause_count: this.pauses.length,
      long_pause_count: longPauses.length,
      total_pause_sec: +totalPause.toFixed(2),
      pauses: this.pauses.map(([a, b]) => [+a.toFixed(2), +b.toFixed(2)]),
    };
  }
}
