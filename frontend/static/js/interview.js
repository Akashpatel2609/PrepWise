// Interview Management JavaScript
class InterviewManager {
  constructor(options = {}) {
    this.sessionId = null;

    // Media
    this.mediaStream = null;
    this.videoRecorder = null;
    this.audioRecorder = null;
    this.isRecording = false;

    // Hooks/callbacks
    this.getQuestionNumber = options.getQuestionNumber || (() => (window.currentQuestionIndex || 1));
    this.getQuestionText   = options.getQuestionText   || (() => (window.currentQuestionText || ''));
    this.onTranscriptMerge = options.onTranscriptMerge || (payload => this.#defaultTranscriptMerge(payload));

    // VAD
    this._isSpeaking = false;
    this._speakStartTs = 0;

    // slicer
    this._sliceTimer = null;
  }

  // config knobs
  static CHUNK_MS = 8000;          // ⬅️ longer chunks = better context
  static AUDIO_BITS = 128000;      // ⬅️ higher bitrate for Opus/MP4

  async start(sessionId = null) {
    this.sessionId = sessionId || (typeof SESSION_ID !== 'undefined' ? SESSION_ID : null);
    await this.#startRecording();
    this.#startAudioLevelUI();
  }
  stop() { this.#stopRecording(); }

  pickAudioMime() {
    const prefs = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/ogg',
      'audio/mp4;codecs=aac', // Safari
      'audio/mp4',
      'audio/mpeg',
      'audio/wav'
    ];
    for (const t of prefs) {
      if (window.MediaRecorder?.isTypeSupported?.(t)) return t;
    }
    return '';
  }

  async sendAudioChunk(blob, { sessionId, questionNumber } = {}) {
    try {
      const sid = sessionId || (window.SESSION_ID ?? this.sessionId ?? '');
      const qn  = questionNumber ?? (window.currentQuestionIndex ?? 1);
      const mime = blob.type || '';

      const name =
        mime.includes('wav')  ? 'chunk.wav'  :
        mime.includes('ogg')  ? 'chunk.ogg'  :
        mime.includes('mp4') || mime.includes('mpeg') ? 'chunk.m4a' :
        'chunk.webm';

      const file = new File([blob], name, { type: mime || 'application/octet-stream' });
      const form = new FormData();
      form.append('audio', file, name);
      form.append('session_id', sid);
      form.append('question_number', qn);
      form.append('mime', mime);
      form.append('lang', 'en'); // optional hint for backend if you wire it

      const API_BASE = window.API_BASE || ''; // e.g. 'http://127.0.0.1:8000'
      const res = await fetch(`${API_BASE}/api/analysis/speech-analysis`, { method: 'POST', body: form });

      const raw = await res.text();
      let data = null;
      try { data = JSON.parse(raw); } catch {
        console.error('Non-JSON from /speech-analysis:', raw.slice(0, 200));
        return;
      }

      if (data?.text) {
        data.text.split(/\s+/).filter(Boolean).forEach(w => console.log('[whisper]', w));
      }

      const speechEl = document.getElementById('speechStatus');
      if (speechEl && data?.analysis?.filler_count >= 0) {
        speechEl.textContent = data.analysis.filler_count > 0
          ? `Filler words detected (${data.analysis.filler_count})`
          : 'Clear speech';
      }

      if (data?.text?.trim()) {
        this.onTranscriptMerge({
          questionNumber: qn,
          questionText: this.getQuestionText(),
          text: data.text.trim(),
          confidence: data.analysis?.confidence ?? 0.9,
        });
      }
    } catch (e) {
      console.error('sendAudioChunk error', e);
    }
  }

  #defaultTranscriptMerge({ questionNumber, questionText, text, confidence }) {
    try {
      const id = window.interviewData || (window.interviewData = {
        total_words: 0,
        total_speaking_time: 0,
        total_questions: window.TOTAL_QUESTIONS || 5,
        questions_answered: 0,
        questions_skipped: 0,
        transcript: [],
        filler_words: { um: 0, uh: 0, like: 0 },
        posture_data: [],
        sample_response: ""
      });

      const now = new Date().toLocaleTimeString();
      const last = id.transcript[id.transcript.length - 1];
      const shouldMerge =
        last &&
        last.question_number === questionNumber &&
        (Date.now() - (last.lastUpdated || 0)) < 7000;

      const qSpeak = (typeof window.speakingTimeForCurrentQuestion === 'number')
        ? window.speakingTimeForCurrentQuestion
        : 0;

      if (shouldMerge) {
        last.response += ' ' + text;
        last.duration = qSpeak;
        last.confidence = Math.max(last.confidence || 0, confidence);
        last.lastUpdated = Date.now();
      } else {
        id.transcript.push({
          question_number: questionNumber,
          question: questionText || '',
          response: text,
          timestamp: now,
          duration: qSpeak,
          confidence,
          lastUpdated: Date.now()
        });
      }

      const words = text.split(/\s+/).filter(Boolean);
      id.total_words += words.length;
      words.forEach(w => {
        const lw = w.toLowerCase().replace(/[^\w]/g, '');
        if (lw === 'um') id.filler_words.um++;
        if (lw === 'uh') id.filler_words.uh++;
        if (lw === 'like') id.filler_words.like++;
      });

      if (!id.sample_response && text.length > 15) id.sample_response = text;
      if (typeof window.currentQuestionIndex === 'number') {
        id.questions_answered = Math.max(id.questions_answered, window.currentQuestionIndex);
      }
    } catch (e) {
      console.warn('default transcript merge failed:', e);
    }
  }

  async #startRecording() {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        // Turn OFF browser DSP to reduce artifacts
        audio: {
          channelCount: 1,
          sampleRate: 48000,
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false
        }
      });

      const videoEl = document.getElementById('interviewWebcam') || document.getElementById('webcam');
      if (videoEl) videoEl.srcObject = this.mediaStream;

      try {
        this.videoRecorder = new MediaRecorder(this.mediaStream, { mimeType: 'video/webm;codecs=vp9' });
        this.videoRecorder.start(1000);
      } catch (e) { console.warn('Video recorder not started:', e?.message || e); }

      const audioTrack = this.mediaStream.getAudioTracks()[0];
      const audioStream = new MediaStream([audioTrack]);
      const audioMime = this.pickAudioMime();

      const startNewRecorder = () => {
        const opts = audioMime ? { mimeType: audioMime, audioBitsPerSecond: InterviewManager.AUDIO_BITS } : { audioBitsPerSecond: InterviewManager.AUDIO_BITS };
        this.audioRecorder = new MediaRecorder(audioStream, opts);

        this.audioRecorder.ondataavailable = (e) => {
          if (e.data && e.data.size) {
            this.sendAudioChunk(e.data, {
              sessionId: window.SESSION_ID || this.sessionId || '',
              questionNumber: window.currentQuestionIndex || 1
            });
          }
        };

        this.audioRecorder.onstop = () => {
          if (this._sliceTimer) { clearTimeout(this._sliceTimer); this._sliceTimer = null; }
          if (this.isRecording) startNewRecorder();
        };

        this.audioRecorder.start(); // manual slice
        this._sliceTimer = setTimeout(() => {
          try { this.audioRecorder.requestData(); } catch {}
          try { this.audioRecorder.stop(); } catch {}
        }, InterviewManager.CHUNK_MS);
      };

      startNewRecorder();
      this.isRecording = true;
      console.log('🎙️ Recording started');
    } catch (err) {
      console.error('Failed to start recording:', err);
      alert('Please allow access to your microphone and camera.');
    }
  }

  #stopRecording() {
    if (this._sliceTimer) { clearTimeout(this._sliceTimer); this._sliceTimer = null; }
    try { if (this.videoRecorder && this.videoRecorder.state !== 'inactive') this.videoRecorder.stop(); } catch(e){}
    try { if (this.audioRecorder && this.audioRecorder.state !== 'inactive') this.audioRecorder.stop(); } catch(e){}
    this.isRecording = false;

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(t => t.stop());
      this.mediaStream = null;
    }
    console.log('⏹️ Recording stopped');
  }

  #startAudioLevelUI() {
    if (!this.mediaStream) return;
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(this.mediaStream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    const buf = new Uint8Array(analyser.frequencyBinCount);
    const speechEl = document.getElementById('speechStatus');

    let above = 0, below = 0;
    const THRESH = 12, START_FR = 3, STOP_FR = 12;

    const loop = (ts) => {
      if (!this.isRecording) { try { audioContext.close(); } catch(e){} return; }
      analyser.getByteFrequencyData(buf);
      const avg = buf.reduce((a,b)=>a+b,0) / buf.length;
      if (speechEl) speechEl.textContent = avg > THRESH ? 'Listening… (audio detected)' : 'Listening…';

      if (avg > THRESH) {
        above++; below = 0;
        if (!this._isSpeaking && above >= START_FR) { this._isSpeaking = true; this._speakStartTs = ts || performance.now(); }
      } else {
        below++; above = 0;
        if (this._isSpeaking && below >= STOP_FR) {
          this._isSpeaking = false;
          const endTs = ts || performance.now();
          const delta = Math.max(0, (endTs - this._speakStartTs) / 1000);
          if (window.interviewData) window.interviewData.total_speaking_time += delta;
          if (typeof window.speakingTimeForCurrentQuestion === 'number') window.speakingTimeForCurrentQuestion += delta;
        }
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }
}

// Question Generator
class QuestionGenerator {
  constructor() {
    this.apiEndpoint = '/api/generate-question';
    this.questions = [];
    this.currentIndex = 0;
  }
  async generateQuestions(jobDescription, count) {
    try {
      const response = await fetch('/api/generate-questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_description: jobDescription, count })
      });
      if (response.ok) {
        const data = await response.json();
        this.questions = data.questions;
        return this.questions;
      }
    } catch (error) { console.error('Error generating questions:', error); }
    return this.getFallbackQuestions(count);
  }
  getFallbackQuestions(count) {
    const fallback = [
      "Tell me about yourself and your background.",
      "What interests you about this role and our company?",
      "Describe a challenging project you've worked on recently.",
      "How do you handle working under pressure and tight deadlines?",
      "What are your greatest strengths and how do they apply to this role?",
      "Describe a time when you had to work with a difficult team member.",
      "Where do you see yourself in 5 years?",
      "Why are you looking to leave your current position?",
      "What is your approach to learning new technologies or skills?",
      "Do you have any questions for us about the role or company?"
    ];
    return fallback.slice(0, count);
  }
  getNextQuestion() { return (this.currentIndex < this.questions.length) ? this.questions[this.currentIndex++] : null; }
  getCurrentQuestionIndex() { return this.currentIndex; }
  getTotalQuestions() { return this.questions.length; }
}

// Timer Management
class TimerManager {
  constructor(minutes, onTimeUp) {
    this.totalSeconds = minutes * 60;
    this.remainingSeconds = this.totalSeconds;
    this.interval = null;
    this.onTimeUp = onTimeUp;
    this.isPaused = false;
  }
  start() {
    this.interval = setInterval(() => {
      if (!this.isPaused) {
        this.remainingSeconds--;
        this.updateDisplay();
        if (this.remainingSeconds <= 0) {
          this.stop();
          if (this.onTimeUp) this.onTimeUp();
        }
      }
    }, 1000);
  }
  pause() { this.isPaused = true; }
  resume() { this.isPaused = false; }
  stop() { if (this.interval) { clearInterval(this.interval); this.interval = null; } }
  reset(minutes) { this.stop(); this.totalSeconds = minutes * 60; this.remainingSeconds = this.totalSeconds; this.updateDisplay(); }
  updateDisplay() {
    const minutes = Math.floor(this.remainingSeconds / 60);
    const seconds = this.remainingSeconds % 60;
    const display = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    const el = document.getElementById('questionTimer');
    if (el) {
      el.textContent = display;
      if (this.remainingSeconds <= 30) el.style.color = '#dc3545';
      else if (this.remainingSeconds <= 60) el.style.color = '#ffc107';
      else el.style.color = '#058ED9';
    }
  }
  getTimeRemaining() { return this.remainingSeconds; }
}

// Global instances
window.interviewManager = new InterviewManager();
window.questionGenerator = new QuestionGenerator();
window.timerManager = null;

// Utils
window.PrepWiseUtils = {
  formatTime: (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  },
  calculateWPM: (text, durationSeconds) => {
    const words = text.split(' ').length;
    const minutes = durationSeconds / 60;
    return Math.round(words / Math.max(minutes, 0.01));
  },
  detectDeviceCapabilities: async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      return {
        camera: devices.some(d => d.kind === 'videoinput'),
        microphone: devices.some(d => d.kind === 'audioinput'),
        speaker: devices.some(d => d.kind === 'audiooutput')
      };
    } catch {
      return { camera: false, microphone: false, speaker: false };
    }
  },
  saveInterviewData: (sessionId, data) => localStorage.setItem(`interview_${sessionId}`, JSON.stringify(data)),
  loadInterviewData: (sessionId) => {
    const data = localStorage.getItem(`interview_${sessionId}`);
    return data ? JSON.parse(data) : null;
  },
  generateSessionId: () => 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9)
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { InterviewManager, QuestionGenerator, TimerManager, PrepWiseUtils };
}
