// src/hooks/useRecorder.js
import { useRef, useState } from "react";

/** Records mic via WebAudio → 16kHz mono WAV. */
export function useRecorder({ onBlob } = {}) {
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState("");

  const streamRef = useRef(null);
  const audioCtxRef = useRef(null);
  const sourceRef = useRef(null);
  const procRef = useRef(null);
  const chunksRef = useRef([]);
  const inputRateRef = useRef(48000);

  async function start() {
    try {
      setError("");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;

      const ctx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: "interactive" });
      audioCtxRef.current = ctx;
      inputRateRef.current = ctx.sampleRate || 48000;

      // *** IMPORTANT: make sure it actually runs (Chrome often starts suspended) ***
      if (ctx.state === "suspended") {
        await ctx.resume();
      }

      const src = ctx.createMediaStreamSource(stream);
      sourceRef.current = src;

      // small gain node to keep the graph "alive"
      const gain = ctx.createGain();
      gain.gain.value = 0; // muted path to destination (prevents feedback)
      src.connect(gain);
      gain.connect(ctx.destination);

      const proc = ctx.createScriptProcessor(4096, 1, 1);
      procRef.current = proc;
      chunksRef.current = [];

      proc.onaudioprocess = (e) => {
        const chan = e.inputBuffer.getChannelData(0);
        chunksRef.current.push(new Float32Array(chan));
      };

      src.connect(proc);
      proc.connect(ctx.destination);

      setRecording(true);
    } catch (e) {
      console.error(e);
      setError(e?.message || "Mic permission failed");
      stop(true);
    }
  }

  function concatFloat32(arrays) {
    const len = arrays.reduce((a, b) => a + b.length, 0);
    const out = new Float32Array(len);
    let off = 0;
    arrays.forEach(a => { out.set(a, off); off += a.length; });
    return out;
  }

  function downsampleTo16k(float32, inRate) {
    const outRate = 16000;
    if (inRate === outRate) return float32;
    const ratio = inRate / outRate;
    const outLen = Math.round(float32.length / ratio);
    const out = new Float32Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const pos = i * ratio;
      const i0 = Math.floor(pos);
      const i1 = Math.min(i0 + 1, float32.length - 1);
      const frac = pos - i0;
      out[i] = float32[i0] * (1 - frac) + float32[i1] * frac;
    }
    return out;
  }

  function floatTo16BitPCM(float32) {
    const buffer = new ArrayBuffer(float32.length * 2);
    const view = new DataView(buffer);
    let offset = 0;
    for (let i = 0; i < float32.length; i++, offset += 2) {
      let s = Math.max(-1, Math.min(1, float32[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return view;
  }

  function encodeWAV(samples, sampleRate) {
    const numChannels = 1, bytesPerSample = 2;
    const blockAlign = numChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataLen = samples.byteLength;

    const buffer = new ArrayBuffer(44 + dataLen);
    const view = new DataView(buffer);

    writeStr(view, 0, "RIFF");
    view.setUint32(4, 36 + dataLen, true);
    writeStr(view, 8, "WAVE");
    writeStr(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeStr(view, 36, "data");
    view.setUint32(40, dataLen, true);

    const pcm = new Uint8Array(buffer, 44);
    for (let i = 0; i < dataLen; i++) pcm[i] = samples.getUint8(i);

    return new Blob([view], { type: "audio/wav" });

    function writeStr(dv, off, s) { for (let i = 0; i < s.length; i++) dv.setUint8(off + i, s.charCodeAt(i)); }
  }

  async function stop(silent = false) {
    try {
      procRef.current?.disconnect();
      sourceRef.current?.disconnect();
      audioCtxRef.current && audioCtxRef.current.state !== "closed" && (await audioCtxRef.current.close());
      streamRef.current?.getTracks().forEach(t => t.stop());
    } catch {}
    setRecording(false);
    if (silent) return;

    try {
      const raw = concatFloat32(chunksRef.current);
      const seconds = raw.length / (inputRateRef.current || 48000);
      if (seconds < 0.25) {
        setError("Mic captured near-zero audio. Please check input device / permissions.");
        return;
      }
      const ds = downsampleTo16k(raw, inputRateRef.current);
      const pcm16 = floatTo16BitPCM(ds);
      const wavBlob = encodeWAV(pcm16, 16000);
      if (wavBlob.size < 800) {
        setError("Encoded audio is too small. Try again.");
        return;
      }
      onBlob && onBlob(wavBlob, "audio/wav");
    } catch (e) {
      console.error(e);
      setError(e?.message || "Encoding error");
    }
  }

  return { start, stop, recording, error };
}
