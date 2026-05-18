// MediaRecorder wrapper + optional Web Speech API live transcript.

export class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.chunks = [];
    this.stream = null;
    this.startedAt = 0;
    this.endedAt = 0;
    this.recognition = null;
    this.liveText = '';
    this.onLiveText = null;
  }

  static isSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  }

  async ensureStream() {
    if (this.stream) return this.stream;
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    return this.stream;
  }

  async start({ onLiveText } = {}) {
    await this.ensureStream();
    this.chunks = [];
    this.liveText = '';
    this.onLiveText = onLiveText;

    const mimeTypes = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
    ];
    let mimeType = '';
    for (const mt of mimeTypes) {
      if (MediaRecorder.isTypeSupported(mt)) { mimeType = mt; break; }
    }

    this.mediaRecorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : {});
    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) this.chunks.push(e.data);
    };
    this.startedAt = performance.now();
    this.mediaRecorder.start();

    this._startSpeechRecognition();
  }

  _startSpeechRecognition() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    try {
      this.recognition = new SR();
      this.recognition.continuous = true;
      this.recognition.interimResults = true;
      this.recognition.lang = 'en-US';
      this.recognition.onresult = (event) => {
        let finalText = '';
        let interimText = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const r = event.results[i];
          if (r.isFinal) finalText += r[0].transcript;
          else interimText += r[0].transcript;
        }
        if (finalText) this.liveText += finalText + ' ';
        const combined = (this.liveText + interimText).trim();
        if (this.onLiveText) this.onLiveText(combined);
      };
      this.recognition.onerror = () => { /* swallow — live display is best-effort */ };
      this.recognition.start();
    } catch (e) {
      this.recognition = null;
    }
  }

  async stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
        resolve({ blob: new Blob(this.chunks, { type: 'audio/webm' }), durationSec: 0 });
        return;
      }
      this.mediaRecorder.onstop = () => {
        this.endedAt = performance.now();
        const blob = new Blob(this.chunks, { type: this.mediaRecorder.mimeType || 'audio/webm' });
        const durationSec = Math.max(0, (this.endedAt - this.startedAt) / 1000);
        resolve({ blob, durationSec });
      };
      this.mediaRecorder.stop();
      if (this.recognition) {
        try { this.recognition.stop(); } catch (e) { /* */ }
        this.recognition = null;
      }
    });
  }

  release() {
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
  }
}
