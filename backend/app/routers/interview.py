from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

# Shared session store (questions asked + per-question transcripts)
try:
    from app.models.session_store import SESSIONS
except Exception:
    SESSIONS = {}

router = APIRouter()

# ---------------------------
# Models
# ---------------------------
class InterviewSessionCreate(BaseModel):
    name: str
    job_description: str
    minutes_per_question: int
    total_time: int

class InterviewSessionResponse(BaseModel):
    session_id: str
    name: str
    job_description: str
    minutes_per_question: int
    total_time: int
    num_questions: int
    created_at: datetime
    status: str

class QuestionResponse(BaseModel):
    question_id: str
    question_text: str
    response_audio_path: Optional[str] = None
    response_video_path: Optional[str] = None
    transcript: Optional[str] = None
    analysis_data: Optional[dict] = None

# ---------------------------
# In-memory store (session metadata + uploads)
# ---------------------------
interview_sessions = {}
question_responses = {}

# ---------------------------
# CRUD for interview sessions (metadata)
# ---------------------------
@router.post("/create", response_model=InterviewSessionResponse)
async def create_interview_session(session_data: InterviewSessionCreate):
    """Create a new interview session (metadata)."""
    try:
        session_id = str(uuid.uuid4())
        num_questions = max(1, session_data.total_time // max(1, session_data.minutes_per_question))

        meta = {
            "session_id": session_id,
            "name": session_data.name,
            "job_description": session_data.job_description,
            "minutes_per_question": session_data.minutes_per_question,
            "total_time": session_data.total_time,
            "num_questions": num_questions,
            "created_at": datetime.now(),
            "status": "created"
        }
        interview_sessions[session_id] = meta

        # Ensure a SESSIONS record exists for Q/A tracking
        SESSIONS.setdefault(session_id, {"asked": [], "transcript": []})

        return InterviewSessionResponse(**meta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")

@router.get("/{session_id}", response_model=InterviewSessionResponse)
async def get_interview_session(session_id: str):
    """Get interview session metadata."""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return InterviewSessionResponse(**interview_sessions[session_id])

@router.post("/{session_id}/start")
async def start_interview_session(session_id: str):
    """Mark a session as in progress."""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    interview_sessions[session_id]["status"] = "in_progress"
    interview_sessions[session_id]["started_at"] = datetime.now()
    # Initialize SESSIONS if missing
    SESSIONS.setdefault(session_id, {"asked": [], "transcript": []})
    return {"message": "Interview session started", "session_id": session_id}

@router.post("/{session_id}/complete")
async def complete_interview_session(session_id: str):
    """Mark a session completed."""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    interview_sessions[session_id]["status"] = "completed"
    interview_sessions[session_id]["completed_at"] = datetime.now()
    return {"message": "Interview session completed", "session_id": session_id}

@router.delete("/{session_id}")
async def delete_interview_session(session_id: str):
    """Delete a session and any associated response uploads."""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del interview_sessions[session_id]

    # Delete associated responses
    responses_to_delete = [
        rid for rid, r in question_responses.items() if r["session_id"] == session_id
    ]
    for rid in responses_to_delete:
        del question_responses[rid]

    # Remove Q/A store
    if session_id in SESSIONS:
        del SESSIONS[session_id]

    return {"message": "Session deleted successfully"}

@router.get("/")
async def list_interview_sessions():
    """List all interview sessions (metadata)."""
    return {"sessions": list(interview_sessions.values())}

# ---------------------------
# Minimal upload endpoint (optional – unused in speech-analysis flow)
# ---------------------------
@router.post("/{session_id}/response")
async def submit_response(
    session_id: str,
    question_id: str,
    audio_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    transcript: Optional[str] = None
):
    """Submit a response for a question (manual upload route; speech-analysis is preferred)."""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    response_id = str(uuid.uuid4())
    audio_path = None
    video_path = None

    # Placeholders – add real storage if you want to keep file artifacts
    if audio_file:
        audio_path = f"recordings/{session_id}_{question_id}_audio.wav"
    if video_file:
        video_path = f"recordings/{session_id}_{question_id}_video.mp4"

    response_data = {
        "response_id": response_id,
        "session_id": session_id,
        "question_id": question_id,
        "audio_path": audio_path,
        "video_path": video_path,
        "transcript": transcript,
        "created_at": datetime.now(),
        "analysis_status": "pending"
    }
    question_responses[response_id] = response_data
    return {"message": "Response submitted", "response_id": response_id}

@router.get("/{session_id}/responses")
async def get_session_responses(session_id: str):
    """Get all uploaded responses for a session (if you used the /response endpoint)."""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session_responses = [r for r in question_responses.values() if r["session_id"] == session_id]
    return {"session_id": session_id, "responses": session_responses}

# ---------------------------
# NEW: expose the Q/A memory used by Feedback (asked + transcript)
# ---------------------------
@router.get("/session/{session_id}")
async def get_runtime_session_store(session_id: str):
    """
    Return the in-memory Q/A state used by the app:
        {
          "asked": ["Q1", "Q2", ...],
          "transcript": [ {question_number, question, response, duration, confidence, timestamp}, ... ],
          "current_question_number": int,
          "current_question": str
        }
    """
    sess = SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found in runtime store")
    return sess
