import asyncio
import json
import logging
import os
import tempfile
import wave
from typing import Dict, List, Optional
import numpy as np
from datetime import datetime
from pathlib import Path
from collections import defaultdict
import threading

# Import the actual speech analysis components
try:
    import whisper
    import scipy.io.wavfile as wavfile  # noqa: F401  (kept for future use)
    SPEECH_ANALYSIS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Speech analysis packages not available: {e}")
    SPEECH_ANALYSIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class RealSpeechAnalyzer:
    """Real speech analyzer using Whisper AI and comprehensive analysis"""

    def __init__(self):
        self.sample_rate = 16000
        self.channels = 1
        self.whisper_model = None

    async def initialize(self):
        """Initialize Whisper model"""
        if SPEECH_ANALYSIS_AVAILABLE:
            try:
                print("🔄 Loading Whisper AI model...")
                self.whisper_model = whisper.load_model("base")
                print("✅ Whisper AI model loaded successfully!")
                return True
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                return False
        return False

    def transcribe_audio_data(self, audio_data: bytes) -> str:
        """Transcribe audio data using Whisper"""
        if not self.whisper_model:
            return ""

        try:
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                # Convert bytes to numpy array (assuming 16-bit PCM)
                _ = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

                # Write to WAV file
                with wave.open(temp_file.name, "wb") as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(audio_data)

                # Transcribe using Whisper
                result = self.whisper_model.transcribe(temp_file.name)
                transcription = result.get("text", "").strip()

            # Clean up temp file
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass

            return transcription

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def analyze_speech_performance(self, transcription: str, duration: float) -> dict:
        """Analyze speech performance with detailed metrics"""

        # Basic metrics
        words = transcription.split() if transcription else []
        word_count = len(words)
        speaking_rate = (word_count / duration * 60.0) if duration > 0 else 0.0

        # Filler word detection
        filler_words = [
            "um", "uh", "er", "ah", "like", "you know", "i mean",
            "sort of", "kind of", "i think", "maybe", "well", "so"
        ]

        text_lower = transcription.lower()
        filler_count = 0
        detected_fillers = []
        filler_breakdown = {"um": 0, "uh": 0, "like": 0, "other": 0}

        for filler in filler_words:
            count = text_lower.count(filler)
            if count > 0:
                filler_count += count
                detected_fillers.append(f"{filler}({count})")
                if filler == "um":
                    filler_breakdown["um"] += count
                elif filler == "uh":
                    filler_breakdown["uh"] += count
                elif filler == "like":
                    filler_breakdown["like"] += count
                else:
                    filler_breakdown["other"] += count

        filler_rate = (filler_count / word_count) if word_count > 0 else 0.0

        # Content score (0–60)
        if word_count >= 60:
            content_score = 60
        elif word_count >= 40:
            content_score = 50
        elif word_count >= 25:
            content_score = 40
        elif word_count >= 15:
            content_score = 30
        else:
            content_score = max(10, word_count * 2)

        # Speaking rate score (0–25)
        if 130 <= speaking_rate <= 170:
            rate_score = 25
        elif 110 <= speaking_rate < 130 or 170 < speaking_rate <= 190:
            rate_score = 20
        elif 90 <= speaking_rate < 110 or 190 < speaking_rate <= 210:
            rate_score = 15
        else:
            rate_score = 10

        # Clarity bonus (0–15)
        clarity_score = 15 if word_count > 0 and transcription else 0

        # Filler penalty (0–20)
        if filler_rate <= 0.02:
            filler_penalty = 0
        elif filler_rate <= 0.05:
            filler_penalty = 5
        elif filler_rate <= 0.10:
            filler_penalty = 10
        else:
            filler_penalty = min(20, filler_count * 2)

        # Final score
        final_score = content_score + rate_score + clarity_score - filler_penalty
        final_score = max(5, min(100, final_score))

        # Performance level
        if final_score >= 80:
            performance_level = "Excellent"
        elif final_score >= 65:
            performance_level = "Good"
        elif final_score >= 50:
            performance_level = "Fair"
        else:
            performance_level = "Needs Improvement"

        return {
            "transcription": transcription,
            "word_count": word_count,
            "speaking_rate": speaking_rate,
            "filler_count": filler_count,
            "filler_rate": filler_rate,
            "filler_breakdown": filler_breakdown,
            "detected_fillers": detected_fillers,
            "final_score": final_score,
            "performance_level": performance_level,
            "duration": duration,
            "components": {
                "content_score": content_score,
                "rate_score": rate_score,
                "clarity_score": clarity_score,
                "filler_penalty": filler_penalty,
            },
        }


class SpeechAnalysisService:
    """Service for analyzing speech data including transcription, filler words, and quality metrics"""

    def __init__(self):
        self.real_analyzer = RealSpeechAnalyzer() if SPEECH_ANALYSIS_AVAILABLE else None
        # In-memory storage of per-session chunks
        self.session_data: Dict[str, List[Dict]] = defaultdict(list)
        self.session_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.use_real_analysis = False

    async def initialize(self):
        """Initialize the speech analysis components"""
        try:
            if self.real_analyzer:
                self.use_real_analysis = await self.real_analyzer.initialize()
                if self.use_real_analysis:
                    logger.info("Real speech analysis service initialized with Whisper AI")
                else:
                    logger.warning("Failed to initialize Whisper AI, falling back to mock analysis")
            else:
                logger.warning("Speech analysis packages not available, using mock analysis")
        except Exception as e:
            logger.error(f"Failed to initialize speech analysis service: {str(e)}")
            self.use_real_analysis = False

    async def cleanup(self):
        """Cleanup resources (placeholder)"""
        logger.info("Speech analysis service cleanup complete")

    async def analyze_audio_chunk(self, audio_data: bytes, session_id: str) -> Dict:
        """Analyze a chunk of audio data in real-time and persist it to the session"""
        try:
            if self.use_real_analysis and self.real_analyzer:
                transcription = self.real_analyzer.transcribe_audio_data(audio_data)
                estimated_duration = (
                    len(audio_data) / (self.real_analyzer.sample_rate * 2)
                    if audio_data else 0.0
                )

                if transcription and transcription.strip():
                    analysis = self.real_analyzer.analyze_speech_performance(
                        transcription, estimated_duration
                    )

                    result = {
                        "transcript_chunk": transcription,
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
                        "duration": estimated_duration,
                        "timestamp": datetime.utcnow().isoformat(),
                        "confidence": 0.9,
                        "analysis_type": "real_whisper_ai",
                    }

                    with self.session_locks[session_id]:
                        self.session_data[session_id].append(result)
                        logger.debug(
                            f"[{session_id}] stored speech chunk (len={len(transcription)}), "
                            f"total={len(self.session_data[session_id])}"
                        )

                    return result

                # No speech detected
                result = {
                    "transcript_chunk": "",
                    "filler_words": {"detected": [], "count": 0, "breakdown": {"um": 0, "uh": 0, "like": 0, "other": 0}},
                    "audio_quality": {"volume_level": 0, "clarity_score": 0, "speaking_rate": 0},
                    "performance_metrics": {"word_count": 0, "filler_rate": 0.0, "final_score": 0, "performance_level": "No speech"},
                    "duration": estimated_duration,
                    "timestamp": datetime.utcnow().isoformat(),
                    "confidence": 1.0,
                    "analysis_type": "real_whisper_ai_no_speech",
                }

                with self.session_locks[session_id]:
                    self.session_data[session_id].append(result)
                    logger.debug(
                        f"[{session_id}] stored silence chunk, total={len(self.session_data[session_id])}"
                    )
                return result

            # Fallback to mock analysis
            result = await self._mock_analysis(audio_data, session_id)
            with self.session_locks[session_id]:
                self.session_data[session_id].append(result)
                logger.debug(
                    f"[{session_id}] stored mock chunk, total={len(self.session_data[session_id])}"
                )
            return result

        except Exception as e:
            logger.error(f"Error in speech analysis: {str(e)}")
            result = await self._mock_analysis(audio_data, session_id)
            with self.session_locks[session_id]:
                self.session_data[session_id].append(result)
            return result

    async def _mock_analysis(self, audio_data: bytes, session_id: str) -> Dict:
        """Fallback mock analysis when real analysis is not available"""
        analysis_result = {
            "transcript_chunk": "Mock transcribed text (install whisper for real analysis)",
            "filler_words": {
                "detected": [],
                "count": 0,
                "breakdown": {"um": 0, "uh": 0, "like": 0, "other": 0},
            },
            "audio_quality": {
                "volume_level": 75,
                "clarity_score": 88,
                "speaking_rate": 150,
            },
            "performance_metrics": {
                "word_count": 25,
                "filler_rate": 0.0,
                "final_score": 75,
                "performance_level": "Mock Analysis",
            },
            "duration": 1.0,  # pretend 1s chunk
            "timestamp": datetime.utcnow().isoformat(),
            "confidence": 0.5,
            "analysis_type": "mock_fallback",
        }
        return analysis_result

    async def analyze_complete_audio(self, audio_file_path: str, session_id: str) -> Dict:
        """Analyze complete audio file for comprehensive metrics"""
        try:
            if self.use_real_analysis and self.real_analyzer:
                with open(audio_file_path, "rb") as f:
                    transcription = self.real_analyzer.transcribe_audio_data(f.read())

                if transcription:
                    # Better to read real duration via librosa or soundfile; using default here
                    estimated_duration = 60.0

                    analysis = self.real_analyzer.analyze_speech_performance(
                        transcription, estimated_duration
                    )

                    return {
                        "transcript": transcription,
                        "summary_metrics": {
                            "total_duration": estimated_duration,
                            "total_words": analysis["word_count"],
                            "speaking_rate_wpm": analysis["speaking_rate"],
                            "filler_count": analysis["filler_count"],
                            "filler_rate": analysis["filler_rate"],
                            "final_score": analysis["final_score"],
                        },
                        "detailed_analysis": analysis,
                        "confidence": 0.9,
                        "analysis_type": "real_whisper_complete",
                    }

            # Fallback mock analysis (keep schema consistent with real path)
            analysis_result = {
                "transcript": "Complete transcript of the interview response (mock)",
                "summary_metrics": {
                    "total_duration": 120.0,
                    "total_words": 185,             # ✅ consistent field name
                    "speaking_rate_wpm": 92.0,
                    "filler_count": 6,
                    "filler_rate": 6 / 185.0,
                    "final_score": 75,
                },
                "detailed_analysis": {
                    "components": {
                        "content_score": 40,
                        "rate_score": 15,
                        "clarity_score": 15,
                        "filler_penalty": 5,
                    }
                },
                "confidence": 0.6,
                "analysis_type": "mock_complete",
            }
            return analysis_result

        except Exception as e:
            logger.error(f"Complete audio analysis error: {str(e)}")
            return {"error": str(e)}

    async def get_session_summary(self, session_id: str) -> Dict:
        """Get comprehensive summary for a session"""
        if session_id not in self.session_data or not self.session_data[session_id]:
            return {"error": "No data found for session"}

        chunks = self.session_data[session_id]

        total_words = sum(c.get("performance_metrics", {}).get("word_count", 0) for c in chunks)
        total_filler = sum(c.get("filler_words", {}).get("count", 0) for c in chunks)
        avg_clarity = float(
            np.mean([c.get("audio_quality", {}).get("clarity_score", 0) for c in chunks])
        )
        total_duration = float(sum(c.get("duration", 0.0) for c in chunks))
        full_transcript = " ".join(
            c.get("transcript_chunk", "").strip()
            for c in chunks
            if c.get("transcript_chunk")
        ).strip()

        speaking_rate_wpm = (total_words / total_duration * 60.0) if total_duration > 0 else 0.0
        filler_rate = (total_filler / total_words) if total_words > 0 else 0.0

        return {
            "session_id": session_id,
            "transcript": full_transcript,
            "summary_metrics": {
                "total_duration": total_duration,
                "total_words": total_words,            # ✅ consistent naming
                "speaking_rate_wpm": speaking_rate_wpm,
                "filler_count": total_filler,
                "filler_rate": filler_rate,
                "average_clarity_score": avg_clarity,
            },
            "chunks": chunks,
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }

    async def detect_filler_words_realtime(self, audio_chunk: bytes) -> Dict:
        """Real-time filler word detection (mock)"""
        detected_fillers = ["um"] if np.random.random() < 0.1 else []
        return {
            "detected_fillers": detected_fillers,
            "confidence": 0.95 if detected_fillers else 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio to text (mock)"""
        return "This is a mock transcription of the user's speech."

    async def analyze_pronunciation(self, audio_data: bytes, expected_text: str = None) -> Dict:
        """Analyze pronunciation quality (mock)"""
        return {
            "pronunciation_score": 88,
            "mispronounced_words": [],
            "accent_analysis": {
                "detected_accent": "neutral",
                "confidence": 0.75,
            },
            "phonetic_accuracy": 92,
        }
