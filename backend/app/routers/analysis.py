from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import List, Optional
import logging
from datetime import datetime
from fastapi.responses import JSONResponse
from collections import defaultdict
import tempfile, subprocess, os

from app.services.speech_service import SpeechAnalysisService

def _ffmpeg_decode_to_wav_16k(src_path: str, dst_path: str) -> None:
    # High-quality resample with soxr + 16k mono PCM16 WAV
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", src_path,
        "-ac", "1",
        "-ar", "16000",
        "-sample_fmt", "s16",
        "-af", "aresample=resampler=soxr:precision=28",
        "-f", "wav", dst_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def _filler_count_from_text(text: str) -> int:
    words = [w.strip(".,?!;:()[]\"'").lower() for w in (text or "").split()]
    return sum(1 for w in words if w in ("um", "uh", "like"))

def _speaking_rate_label(rate) -> str:
    try:
        r = float(rate)
    except Exception:
        return str(rate or "normal")
    if r <= 110: return "Too slow"
    if r <= 160: return "Good pace"
    return "Too fast"

router = APIRouter()
logger = logging.getLogger(__name__)
speech_service = SpeechAnalysisService()

class AnalysisRequest(BaseModel):
    session_id: str
    data_type: str
    data: dict

class AnalysisResponse(BaseModel):
    analysis_id: str
    session_id: str
    analysis_type: str
    results: dict
    confidence_score: float
    timestamp: str

class FeedbackReport(BaseModel):
    session_id: str
    overall_score: int
    speech_analysis: dict
    body_language_analysis: dict
    recommendations: List[str]
    detailed_metrics: dict

analysis_results = {}
session_summaries = defaultdict(lambda: {
    "chunks": [], "total_words": 0, "total_duration": 0.0,
    "filler": {"um": 0, "uh": 0, "like": 0},
    "rates": [], "clarities": [], "confidences": []
})

@router.post("/audio", response_model=AnalysisResponse)
async def analyze_audio(request: AnalysisRequest):
    try:
        speech_results = {
            "transcript": "This is a sample transcript of the user's response...",
            "filler_words": {"um": 2, "uh": 1, "like": 3},
            "speaking_pace": "normal", "clarity_score": 85,
            "volume_level": "appropriate", "pronunciation_issues": []
        }
        analysis_id = f"audio_{request.session_id}_{len(analysis_results)}"
        response = AnalysisResponse(
            analysis_id=analysis_id, session_id=request.session_id, analysis_type="audio",
            results=speech_results, confidence_score=0.92, timestamp=str(datetime.now())
        )
        analysis_results[analysis_id] = response.dict()
        return response
    except Exception as e:
        logger.error(f"Audio analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {str(e)}")

@router.post("/speech-analysis")
async def analyze_speech_file(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    question_number: Optional[int] = Form(None),
    mime: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
):
    tmp_in = None
    tmp_wav = None
    try:
        mt = (mime or audio.content_type or "").lower()
        logger.info("Received audio: %s (mime=%s) session=%s q=%s", audio.filename, mt, session_id, str(question_number))

        if not getattr(speech_service, "initialized", False):
            await speech_service.initialize()
            speech_service.initialized = True

        raw_bytes = await audio.read()

        if   "wav"  in mt: suffix = ".wav"
        elif "ogg"  in mt: suffix = ".ogg"
        elif "webm" in mt: suffix = ".webm"
        elif "mp4"  in mt or "mpeg" in mt or "m4a" in mt: suffix = ".m4a"
        else: suffix = os.path.splitext(audio.filename or "")[-1] or ".bin"

        tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_in.write(raw_bytes); tmp_in.flush(); tmp_in.close()
        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav"); tmp_wav.close()

        try:
            _ffmpeg_decode_to_wav_16k(tmp_in.name, tmp_wav.name)
            with open(tmp_wav.name, "rb") as f:
                wav_bytes = f.read()
            analysis_result = await speech_service.analyze_audio_chunk(wav_bytes, session_id)
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or b"").decode("utf-8", errors="ignore")
            logger.error("ffmpeg decode failed: %s", detail)
            try:
                analysis_result = await speech_service.analyze_audio_chunk(raw_bytes, session_id)
            except Exception:
                return JSONResponse({
                    "ok": False, "error": "ffmpeg_decode_failed", "detail": detail,
                    "session_id": session_id, "question_number": question_number,
                    "text": "", "analysis": {"filler_count": 0, "confidence": 0.0},
                }, status_code=200)

        transcript_text = (analysis_result.get("transcript_chunk")
                           or analysis_result.get("text")
                           or analysis_result.get("transcript")
                           or "").strip()

        if transcript_text:
            for w in transcript_text.split():
                logger.debug("[session %s] word: %s", session_id, w)

        perf = analysis_result.get("performance_metrics", {}) or {}
        aq   = analysis_result.get("audio_quality", {}) or {}
        fw   = analysis_result.get("filler_words", {}) or {}
        breakdown = fw.get("breakdown", {}) or {}

        filler_count = (
            int(breakdown.get("um", 0) or 0) +
            int(breakdown.get("uh", 0) or 0) +
            int(breakdown.get("like", 0) or 0)
        )
        if filler_count == 0 and transcript_text:
            filler_count = _filler_count_from_text(transcript_text)

        clarity_score = int(aq.get("clarity_score", 0) or 0)
        speaking_rate = aq.get("speaking_rate", 0) or 0
        volume_level  = aq.get("volume_level", "") or "unknown"
        duration      = float(analysis_result.get("duration", 0.0) or 0.0)
        confidence    = float(analysis_result.get("confidence", 0.9) or 0.9)

        normalized_results = {
            "transcript": transcript_text,
            "filler_words": {
                "um": int(breakdown.get("um", 0) or 0),
                "uh": int(breakdown.get("uh", 0) or 0),
                "like": int(breakdown.get("like", 0) or 0),
                "total": int(filler_count),
            },
            "speaking_pace": speaking_rate,
            "clarity_score": clarity_score,
            "volume_level": volume_level,
            "pronunciation_issues": [],
            "final_score": int(perf.get("final_score", 0) or 0),
            "performance_level": perf.get("performance_level", "Unknown"),
            "word_count": int(perf.get("word_count", 0) or 0),
            "duration": duration,
            "question_number": question_number,
        }

        analysis_id = f"audio_{session_id}_{len(analysis_results)}"
        record = AnalysisResponse(
            analysis_id=analysis_id, session_id=session_id, analysis_type="audio",
            results=normalized_results, confidence_score=confidence, timestamp=datetime.now().isoformat()
        ).dict()
        analysis_results[analysis_id] = record

        words = len([w for w in (transcript_text or "").split() if w.strip()])
        s = session_summaries[session_id]
        s["chunks"].append({
            "question_number": question_number, "text": transcript_text, "words": words,
            "duration": duration, "confidence": confidence, "timestamp": record["timestamp"],
        })
        s["total_words"] += words
        s["total_duration"] += duration
        s["filler"]["um"]  += normalized_results["filler_words"]["um"]
        s["filler"]["uh"]  += normalized_results["filler_words"]["uh"]
        s["filler"]["like"]+= normalized_results["filler_words"]["like"]
        if isinstance(speaking_rate, (int, float)): s["rates"].append(float(speaking_rate))
        if isinstance(clarity_score,  (int, float)): s["clarities"].append(float(clarity_score))
        s["confidences"].append(confidence)

        logger.info("Speech analysis stored for session %s (analysis_id=%s)", session_id, analysis_id)

        return {
            "ok": True, "status": "success",
            "session_id": session_id, "question_number": question_number,
            "text": transcript_text,
            "analysis": {"filler_count": int(filler_count), "confidence": confidence},
            "timestamp": record["timestamp"]
        }

    except Exception as e:
        logger.error(f"Speech analysis error: {str(e)}")
        return JSONResponse({
            "ok": False, "error": "transcription_failed", "detail": str(e),
            "session_id": session_id, "question_number": question_number,
            "text": "", "analysis": {"filler_count": 0, "confidence": 0.0},
        }, status_code=200)
    finally:
        for p in ((tmp_in.name if tmp_in else None), (tmp_wav.name if tmp_wav else None)):
            if p:
                try: os.unlink(p)
                except: pass

@router.get("/summary/{session_id}")
async def get_realtime_summary(session_id: str):
    s = session_summaries.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="No summary yet for session")
    combined_text = " ".join(ch["text"] for ch in s["chunks"] if ch["text"])
    return {
        "session_id": session_id,
        "combined_text": combined_text,
        "total_words": s["total_words"],
        "total_duration": s["total_duration"],
        "filler": s["filler"],
        "chunks": s["chunks"],
    }

@router.post("/video", response_model=AnalysisResponse)
async def analyze_video(request: AnalysisRequest):
    try:
        video_results = {
            "posture_score": 78,
            "posture_classification": "good",
            "eye_contact_score": 82,
            "gesture_analysis": { "appropriate_gestures": 85, "fidgeting_detected": False, "hand_position": "appropriate" },
            "facial_expression": { "confidence_level": "moderate", "engagement_score": 88, "emotion_detected": "neutral" },
            "movement_analysis": { "stability": "stable", "excessive_movement": False }
        }
        analysis_id = f"video_{request.session_id}_{len(analysis_results)}"
        response = AnalysisResponse(
            analysis_id=analysis_id,
            session_id=request.session_id,
            analysis_type="video",
            results=video_results,
            confidence_score=0.87,
            timestamp=str(datetime.now())
        )
        analysis_results[analysis_id] = response.dict()
        return response
    except Exception as e:
        logger.error(f"Video analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Video analysis failed: {str(e)}")

@router.get("/session/{session_id}")
async def get_session_analysis(session_id: str):
    session_analyses = [a for a in analysis_results.values() if a["session_id"] == session_id]
    if not session_analyses:
        raise HTTPException(status_code=404, detail="No analysis found for session")
    return {"session_id": session_id, "analyses": session_analyses}

@router.get("/report/{session_id}", response_model=None)
async def generate_feedback_report(session_id: str):
    try:
        session_analyses = [a for a in analysis_results.values() if a["session_id"] == session_id]
        if not session_analyses:
            raise HTTPException(status_code=404, detail="No analysis data found for session")

        audio_analyses = [a for a in session_analyses if a["analysis_type"] == "audio"]
        video_analyses = [a for a in session_analyses if a["analysis_type"] == "video"]

        s = session_summaries.get(session_id, {
            "chunks": [], "total_words": 0, "total_duration": 0.0,
            "filler": {"um":0,"uh":0,"like":0}, "rates": [], "clarities": [], "confidences": []
        })

        from collections import defaultdict as _dd
        by_q = _dd(list)
        for ch in s["chunks"]:
            qn = ch.get("question_number") or 1
            by_q[qn].append(ch)

        transcript = []
        for qn in sorted(by_q.keys()):
            items = by_q[qn]
            text = " ".join(i.get("text", "") for i in items if i.get("text"))
            words = sum(i.get("words", 0) for i in items) or len(text.split())
            duration = sum(i.get("duration", 0.0) for i in items)
            confidence = (sum(i.get("confidence", 0.0) for i in items) / max(1, len(items)))
            ts = items[0].get("timestamp", "") if items else ""

            # 🚫 filter out ghost rows (tiny/no content)
            if words < 5 and duration < 1.0 and len(text.strip()) < 12:
                continue

            transcript.append({
                "question": f"Response to Question {qn}",
                "response": text,
                "timestamp": ts.split("T")[-1][:8] if ts else "",
                "duration": duration,
                "confidence": confidence
            })

        avg_rate    = (sum(s["rates"]) / len(s["rates"])) if s["rates"] else 0.0
        avg_clarity = (sum(s["clarities"]) / len(s["clarities"])) if s["clarities"] else 0.0
        avg_conf    = (sum(s["confidences"]) / len(s["confidences"])) if s["confidences"] else 0.5

        speech_score       = int(min(100, max(0, avg_clarity)))
        body_language_score= 50 if not video_analyses else 78
        overall_score      = int((speech_score + body_language_score) / 2)

        response_time_score= 80 if _speaking_rate_label(avg_rate) == "Good pace" else (40 if _speaking_rate_label(avg_rate) == "Too slow" else 60)
        confidence_score   = int(round(avg_conf * 100))
        content_score      = 70

        payload = {
            "session_id": session_id,
            "overall_score": overall_score,
            "speech_analysis": {
                "score": speech_score,
                "speaking_pace": _speaking_rate_label(avg_rate),
                "clarity": int(avg_clarity),
                "filler_words": {
                    "um": s["filler"]["um"],
                    "uh": s["filler"]["uh"],
                    "like": s["filler"]["like"]
                }
            },
            "body_language": {
                "posture_score": body_language_score,
                "eye_contact": "Good",
                "gestures": "Appropriate"
            },
            "response_time_score": response_time_score,
            "confidence_score": confidence_score,
            "content_score": content_score,
            "transcript": transcript,
            "total_words": s["total_words"],
            "posture_data": [
                {"posture_class": "Good Posture"},
                {"posture_class": "Nervous Expression"},
                {"posture_class": "Confident Expression"},
                {"posture_class": "Slouching"},
                {"posture_class": "Good Posture"}
            ]
        }
        return payload
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@router.get("/metrics/{session_id}")
async def get_session_metrics(session_id: str):
    session_analyses = [a for a in analysis_results.values() if a["session_id"] == session_id]
    if not session_analyses:
        raise HTTPException(status_code=404, detail="No analysis found for session")
    metrics = {
        "total_analyses": len(session_analyses),
        "audio_analyses": len([a for a in session_analyses if a["analysis_type"] == "audio"]),
        "video_analyses": len([a for a in session_analyses if a["analysis_type"] == "video"]),
        "average_confidence": sum([a["confidence_score"] for a in session_analyses]) / len(session_analyses),
        "latest_analysis": max(session_analyses, key=lambda x: x["timestamp"])["timestamp"]
    }
    return {"session_id": session_id, "metrics": metrics}
