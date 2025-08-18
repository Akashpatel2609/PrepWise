# app/routers/analysis.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from app.services.speech_service import SpeechAnalysisService

router = APIRouter()
log = logging.getLogger(__name__)

speech_service = SpeechAnalysisService()

@router.on_event("startup")
async def _init_services():
    await speech_service.initialize()

# ------------ Speech (multipart) -------------
@router.post("/speech-analysis")
async def speech_analysis(
    session_id: str = Form(...),
    question_number: int = Form(...),
    audio: UploadFile = File(...),
):
    try:
        data = await audio.read()
        chunk = await speech_service.analyze_chunk(data, session_id)
        # shape compatible with your frontend:
        return {
            "ok": True,
            "session_id": session_id,
            "question_number": question_number,
            "text": chunk.get("transcript_chunk", ""),
            "analysis": {
                "duration": chunk.get("duration", 0.0),
                "filler_count": chunk.get("filler_words", {}).get("breakdown", {}),
                "confidence": chunk.get("confidence", 0.0),
            },
        }
    except Exception as e:
        log.exception("speech-analysis failed")
        raise HTTPException(status_code=500, detail=str(e))

# ------------ Grade (JSON) accepts camel+snake -------------
class GradeReq(BaseModel):
    session_id: str = Field(..., alias="sessionId")
    question_text: str = Field(..., alias="questionText")
    transcript: str = ""
    job_description: Optional[str] = Field("", alias="jobDescription")
    filler_counts: Dict[str, int] = Field(default_factory=dict, alias="fillerCounts")
    duration_seconds: Optional[float] = Field(None, alias="durationSeconds")

    class Config:
        allow_population_by_field_name = True
        allow_population_by_alias = True

@router.post("/grade-answer")
async def grade_answer(req: GradeReq):
    # Minimal “Gemini-like” response; you can wire Gemini here later.
    transcript = (req.transcript or "").strip()
    if not transcript:
        return {
            "ok": True,
            "summary": "Couldn’t detect any speech. Try again with your mic enabled.",
            "metrics": {
                "content_score": 0, "relevance": 0, "clarity": 0, "structure": 0,
                "length_ok": False, "fillers": req.filler_counts or {}, "pace": "unknown",
            },
            "suggestions": [
                "Confirm your microphone permissions.",
                "Aim for a 45–90s answer using STAR.",
                "Include one measurable result (e.g., %, $, users).",
            ],
        }

    # Simple heuristic grading (placeholder)
    wc = len(transcript.split())
    content = min(100, wc * 2)
    clarity = 70 if wc > 20 else 50
    relevance = 75
    structure = 70
    length_ok = 45 <= wc <= 180

    return {
        "ok": True,
        "summary": "Strong start. Tighten the story and quantify the impact.",
        "metrics": {
            "content_score": content,
            "relevance": relevance,
            "clarity": clarity,
            "structure": structure,
            "length_ok": length_ok,
            "fillers": req.filler_counts or {},
            "pace": "balanced",
        },
        "suggestions": [
            "Lead with a one-line headline of your accomplishment.",
            "Use STAR: Situation, Task, Action, Result.",
            "Add measurable impact (%, $, time, users).",
        ],
    }

# ------------ Video pings (stubs to stop 404s) -------------
# very simple per-session posture tallies
_posture_tallies: Dict[str, Dict[str, int]] = {}

@router.post("/video-frame")
async def video_frame(
    session_id: str = Form(...),
    frame: UploadFile = File(...),
):
    # You can add OpenCV/Mediapipe here. For now, just count a fake label.
    tallies = _posture_tallies.setdefault(session_id, {})
    tallies["Neutral"] = tallies.get("Neutral", 0) + 1
    return {"ok": True}

@router.get("/posture-summary/{session_id}")
async def posture_summary(session_id: str):
    tallies = _posture_tallies.get(session_id, {})
    total = sum(tallies.values()) or 1
    percent = {k: round(v * 100 / total) for k, v in tallies.items()}
    summary = [{"label": k, "count": v} for k, v in tallies.items()]
    return {"ok": True, "session_id": session_id, "percent": percent, "summary": summary}

# ------------ Feedback report -------------
@router.get("/report/{session_id}")
async def feedback_report(session_id: str):
    summary = await speech_service.session_summary(session_id)
    if "error" in summary:
        raise HTTPException(status_code=404, detail="No data")

    # roll up fillers by type from chunks
    U = H = L = 0
    for c in summary["chunks"]:
        bd = c.get("filler_words", {}).get("breakdown", {})
        U += bd.get("um", 0) or 0
        H += bd.get("uh", 0) or 0
        L += bd.get("like", 0) or 0

    # Simple overall scores
    speech_score = min(100, int(summary["summary_metrics"]["speaking_rate_wpm"] / 2) + 50)
    posture_score = 80 if _posture_tallies.get(session_id) else 60
    overall = int((speech_score + posture_score) / 2)

    # Single “question” using the complete transcript; if you track questions, replace this.
    per_questions = [{
        "question_number": 1,
        "question": "Response",
        "filler": {"um": U, "uh": H, "like": L},
        "transcript": summary.get("transcript", ""),
        "what_to_fix": ["Cut fluff", "Quantify outcomes"],
        "how_to_improve": ["Use STAR", "Lead with headline", "Add one metric"],
    }]

    return {
        "session_id": session_id,
        "overall_score": overall,
        "speech_score": speech_score,
        "posture_score": posture_score,
        "filler_totals": {"um": U, "uh": H, "like": L},
        "posture_summary": [{"label": k, "count": v} for k, v in _posture_tallies.get(session_id, {}).items()],
        "per_questions": per_questions,
    }
