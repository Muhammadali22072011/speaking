// Speech synthesis helper for voicing prompts aloud.
// Uses the browser's built-in SpeechSynthesis API — no external service.

const STORAGE_KEY = 'speaking.voiceover.enabled';

class SpeechController {
  constructor() {
    this.supported = typeof window !== 'undefined' && 'speechSynthesis' in window;
    this.enabled = this._loadEnabled();
    this._voices = [];
    this._voicePromise = null;
    this._currentUtterance = null;
    if (this.supported) this._loadVoices();
  }

  _loadEnabled() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      return v === null ? true : v === '1';
    } catch (e) { return true; }
  }

  _saveEnabled() {
    try { localStorage.setItem(STORAGE_KEY, this.enabled ? '1' : '0'); } catch (e) {}
  }

  setEnabled(on) {
    this.enabled = !!on;
    this._saveEnabled();
    if (!this.enabled) this.cancel();
  }

  toggle() {
    this.setEnabled(!this.enabled);
    return this.enabled;
  }

  _loadVoices() {
    const synth = window.speechSynthesis;
    const fill = () => {
      const v = synth.getVoices();
      if (v && v.length) this._voices = v;
    };
    fill();
    if (!this._voices.length) {
      this._voicePromise = new Promise((resolve) => {
        const onChange = () => { fill(); resolve(); };
        synth.addEventListener('voiceschanged', onChange, { once: true });
        setTimeout(() => { fill(); resolve(); }, 600);
      });
    }
  }

  _pickVoice() {
    if (!this._voices.length) return null;
    const en = this._voices.filter((v) => /^en[-_]/i.test(v.lang));
    const preferred = [
      /Google.*UK English Female/i,
      /Google.*US English/i,
      /Microsoft.*Aria/i,
      /Microsoft.*Jenny/i,
      /Samantha/i,
      /Karen/i,
      /Daniel/i,
    ];
    for (const re of preferred) {
      const hit = en.find((v) => re.test(v.name));
      if (hit) return hit;
    }
    return en[0] || this._voices[0];
  }

  cancel() {
    if (!this.supported) return;
    try { window.speechSynthesis.cancel(); } catch (e) {}
    this._currentUtterance = null;
  }

  // Speak a chunk of text. Returns a promise that resolves when done or cancelled.
  async speak(text, { rate = 0.95, pitch = 1.0, volume = 1.0 } = {}) {
    if (!this.supported || !this.enabled || !text) return;
    if (this._voicePromise) { await this._voicePromise; this._voicePromise = null; }
    this.cancel();
    const synth = window.speechSynthesis;
    const utter = new SpeechSynthesisUtterance(text);
    const v = this._pickVoice();
    if (v) { utter.voice = v; utter.lang = v.lang; }
    else { utter.lang = 'en-US'; }
    utter.rate = rate;
    utter.pitch = pitch;
    utter.volume = volume;
    this._currentUtterance = utter;
    return new Promise((resolve) => {
      utter.onend = () => { if (this._currentUtterance === utter) this._currentUtterance = null; resolve(); };
      utter.onerror = () => { if (this._currentUtterance === utter) this._currentUtterance = null; resolve(); };
      synth.speak(utter);
    });
  }
}

export const speech = new SpeechController();

// Build a single spoken script from a prompt payload.
export function promptToSpeech(prompt) {
  if (!prompt || !prompt.data) return '';
  const d = prompt.data;
  if (prompt.type === 'personal') return d.text || '';
  if (prompt.type === 'compare') {
    const pic1 = d.pic1?.label || 'picture one';
    const pic2 = d.pic2?.label || 'picture two';
    const qs = (d.questions || []).join(' ');
    return `Look at the two pictures: ${pic1}, and ${pic2}. ${qs}`;
  }
  if (prompt.type === 'long_turn') {
    const label = d.picture?.label || 'this topic';
    const qs = (d.questions || []).join(' ');
    return `Your topic is: ${label}. ${qs}`;
  }
  if (prompt.type === 'for_against') {
    const topic = d.topic || 'this statement';
    return `Discuss the following topic. ${topic}. Pick two points from each side, give a balanced argument, and reach a conclusion.`;
  }
  return '';
}
