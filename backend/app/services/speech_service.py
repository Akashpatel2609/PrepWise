# app/services/speech_service.py
import asyncio
import logging
import os
import tempfile
import wave
import subprocess
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)

try:
    import whisper  # pip install openai-whisper
    SPEECH_ANALYSIS_AVAILABLE = True
except Exception as e:
    logger.warning(f"Whisper unavailable: {e}")
    whisper = None
    SPEECH_ANALYSIS_AVAILABLE = False


def _run_ffmpeg_decode_to_wav(audio_bytes: bytes, target_sr=16000) -> (str, float):
    """
    Decode arbitrary compressed audio (webm/opus, m4a/mp4, etc.) into a temp mono 16k WAV.
    Returns (wav_path, duration_seconds).
    """
    if not audio_bytes:
        raise ValueError("Empty audio upload")

    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_wav_path = tmp_wav.name
    tmp_wav.close()

    # ffmpeg: read from stdin (pipe:0), write WAV to tmp_wav_path
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-y",
        "-i", "pipe:0",
        "-ac", "1",
        "-ar", str(target_sr),
        tmp_wav_path,
    ]
    try:
        # Run in a subprocess, provide bytes on stdin
        proc = subprocess.run(
            cmd, input=audio_bytes, capture_output=True, check=True
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="ignore") if e.stderr else ""
        try:
            os.unlink(tmp_wav_path)
        except Exception:
            pass
        raise RuntimeError(f"ffmpeg decode failed: {stderr}") from e

    # Compute duration from decoded wav header
    try:
        with wave.open(tmp_wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate() or target_sr
            duration = frames / float(rate) if rate else 0.0
    except Exception:
        duration = 0.0

    return tmp_wav_path, duration


class _WhisperSingleton:
    _model = None

    @classmethod
    def get(cls):
        if cls._model is None and SPEECH_ANALYSIS_AVAILABLE:
            logger.info("Loading Whisper model: base")
            cls._model = whisper.load_model("base")
        return cls._model


class SpeechAnalysisService:
    """
    Robust speech service:
    - decodes browser uploads with ffmpeg
    - transcribes with Whisper
    - computes filler & pacing metrics
    - aggregates per session
    """

    def __init__(self):
        self.session_data: Dict[str, List[Dict]] = defaultdict(list)

    async def initialize(self):
        # Warm the model in a thread so startup isn't blocked
        if SPEECH_ANALYSIS_AVAILABLE:
            try:
                await asyncio.to_thread(_WhisperSingleton.get)
                logger.info("Whisper ready")
            except Exception as e:
                logger.exception(f"Failed to load Whisper: {e}")

    async def analyze_chunk(self, audio_bytes: bytes, session_id: str) -> Dict:
        """
        Main entry: take raw uploaded bytes, decode -> wav, transcribe -> metrics, store in session.
        """
        if not audio_bytes:
            return self._empty_chunk(0.0, session_id, reason="no-bytes")

        try:
            wav_path, duration = await asyncio.to_thread(_run_ffmpeg_decode_to_wav, audio_bytes, 16000)
        except Exception as e:
            logger.error(f"ffmpeg decode error: {e}")
            return self._empty_chunk(0.0, session_id, reason="decode-error")

        text = ""
        try:
            model = _WhisperSingleton.get()
            if model:
                # Run Whisper in a thread (cpu bound)
                result = await asyncio.to_thread(model.transcribe, wav_path)
                text = (result.get("text") or "").strip()
        except Exception as e:
            logger.error(f"Whisper transcribe error: {e}")
        finally:
            try:
                os.unlink(wav_path)
            except Exception:
                pass

        if not text:
            chunk = self._empty_chunk(duration, session_id, reason="no-speech")
            self.session_data[session_id].append(chunk)
            return chunk

        analysis = self._analyze_text(text, duration)
        chunk = {
            "transcript_chunk": text,
            "filler_words": {
                "detected": analysis["detected_fillers"],
                "count": analysis["filler_count"],
                "breakdown": analysis["filler_breakdown"],
            },
            "audio_quality": {
                "volume_level": 75,  # placeholder
                "clarity_score": analysis["components"]["clarity_score"],
                "speaking_rate": analysis["speaking_rate"],
            },
            "performance_metrics": {
                "word_count": analysis["word_count"],
                "filler_rate": analysis["filler_rate"],
                "final_score": analysis["final_score"],
                "performance_level": analysis["performance_level"],
            },
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": 0.9,
            "analysis_type": "whisper",
        }
        self.session_data[session_id].append(chunk)
        return chunk

    def _empty_chunk(self, duration: float, session_id: str, reason: str) -> Dict:
        return {
            "transcript_chunk": "",
            "filler_words": {"detected": [], "count": 0, "breakdown": {"um": 0, "uh": 0, "like": 0, "other": 0}},
            "audio_quality": {"volume_level": 0, "clarity_score": 0, "speaking_rate": 0},
            "performance_metrics": {"word_count": 0, "filler_rate": 0.0, "final_score": 0, "performance_level": reason},
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": 1.0 if reason != "decode-error" else 0.0,
            "analysis_type": "empty",
        }

    def _analyze_text(self, transcription: str, duration: float) -> dict:
        words = transcription.split() if transcription else []
        wc = len(words)
        wpm = (wc / duration * 60.0) if duration > 0 else 0.0

        fillers = ["um", "uh", "er", "ah", "like", "you know", "i mean", "sort of", "kind of", "i think", "maybe", "well", "so"]
        tl = transcription.lower()
        fcount = 0
        detected = []
        breakdown = {"um": 0, "uh": 0, "like": 0, "other": 0}
        for f in fillers:
            c = tl.count(f)
            if c:
                fcount += c
                detected.append(f"{f}({c})")
                if f in ("um", "uh", "like"):
                    breakdown[f] += c
                else:
                    breakdown["other"] += c
        frate = (fcount / wc) if wc > 0 else 0.0

        # content score
        if wc >= 60: content = 60
        elif wc >= 40: content = 50
        elif wc >= 25: content = 40
        elif wc >= 15: content = 30
        else: content = max(10, wc * 2)

        # rate score
        if 130 <= wpm <= 170: rate = 25
        elif 110 <= wpm < 130 or 170 < wpm <= 190: rate = 20
        elif  90 <= wpm < 110 or 190 < wpm <= 210: rate = 15
        else: rate = 10

        clarity = 15 if wc > 0 else 0

        # filler penalty
        if frate <= 0.02: pen = 0
        elif frate <= 0.05: pen = 5
        elif frate <= 0.10: pen = 10
        else: pen = min(20, fcount * 2)

        final = max(5, min(100, content + rate + clarity - pen))
        level = "Excellent" if final >= 80 else "Good" if final >= 65 else "Fair" if final >= 50 else "Needs Improvement"

        return {
            "transcription": transcription,
            "word_count": wc,
            "speaking_rate": wpm,
            "filler_count": fcount,
            "filler_rate": frate,
            "filler_breakdown": breakdown,
            "detected_fillers": detected,
            "final_score": final,
            "performance_level": level,
            "duration": duration,
            "components": {
                "content_score": content,
                "rate_score": rate,
                "clarity_score": clarity,
                "filler_penalty": pen,
            },
        }

    async def session_summary(self, session_id: str) -> Dict:
        chunks = self.session_data.get(session_id) or []
        if not chunks:
            return {"error": "no-data", "session_id": session_id}

        total_words = sum(c.get("performance_metrics", {}).get("word_count", 0) for c in chunks)
        total_filler = sum(c.get("filler_words", {}).get("count", 0) for c in chunks)
        total_duration = sum(c.get("duration", 0.0) for c in chunks)
        clarity_vals = [c.get("audio_quality", {}).get("clarity_score", 0) for c in chunks]
        avg_clarity = float(np.mean(clarity_vals)) if clarity_vals else 0.0

        transcript = " ".join([c.get("transcript_chunk", "") for c in chunks if c.get("transcript_chunk")]).strip()
        wpm = (total_words / total_duration * 60.0) if total_duration > 0 else 0.0
        fr = (total_filler / total_words) if total_words > 0 else 0.0

        return {
            "session_id": session_id,
            "transcript": transcript,
            "summary_metrics": {
                "total_duration": total_duration,
                "total_words": total_words,
                "speaking_rate_wpm": wpm,
                "filler_count": total_filler,
                "filler_rate": fr,
                "average_clarity_score": avg_clarity,
            },
            "chunks": chunks,
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }
