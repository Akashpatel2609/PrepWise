from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import uuid, os, shutil, logging

router = APIRouter()
logger = logging.getLogger(__name__)

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

interview_sessions: Dict[str, dict] = {}
question_responses: Dict[str, dict] = {}

def _ensure_session_minimal(session_id: str) -> dict:
    """Create a minimal session if the backend restarted and memory is empty."""
    s = interview_sessions.get(session_id)
    if s:
        return s
    s = {
        "session_id": session_id,
        "name": "Candidate",
        "job_description": "",
        "minutes_per_question": 1,
        "total_time": 1,
        "num_questions": 1,
        "created_at": datetime.now(),
        "status": "in_progress",
        "started_at": datetime.now(),
    }
    interview_sessions[session_id] = s
    logger.info("Recovered minimal session for %s", session_id)
    return s

@router.post("/create", response_model=InterviewSessionResponse)
async def create_interview_session(session_data: InterviewSessionCreate):
    try:
        session_id = str(uuid.uuid4())
        num_questions = max(1, session_data.total_time // max(1, session_data.minutes_per_question))
        session = {
            "session_id": session_id,
            "name": session_data.name,
            "job_description": session_data.job_description,
            "minutes_per_question": max(1, session_data.minutes_per_question),
            "total_time": max(1, session_data.total_time),
            "num_questions": num_questions,
            "created_at": datetime.now(),
            "status": "created",
        }
        interview_sessions[session_id] = session
        return InterviewSessionResponse(**session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")

@router.get("/{session_id}", response_model=InterviewSessionResponse)
async def get_interview_session(session_id: str):
    s = interview_sessions.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return InterviewSessionResponse(**s)

@router.post("/{session_id}/start")
async def start_interview_session(session_id: str):
    s = interview_sessions.get(session_id)
    if not s:
        s = _ensure_session_minimal(session_id)
    s["status"] = "in_progress"
    s["started_at"] = datetime.now()
    return {"message": "Interview session started", "session_id": session_id}

@router.post("/{session_id}/complete")
async def complete_interview_session(session_id: str):
    # Never 404 here — recover if needed
    s = interview_sessions.get(session_id) or _ensure_session_minimal(session_id)
    s["status"] = "completed"
    s["completed_at"] = datetime.now()
    return {"ok": True, "message": "Interview session completed", "session_id": session_id}

@router.post("/{session_id}/response")
async def submit_response(
    session_id: str,
    question_id: str = Form(...),
    audio_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    transcript: Optional[str] = Form(None),
):
    if session_id not in interview_sessions:
        _ensure_session_minimal(session_id)

    response_id = str(uuid.uuid4())
    os.makedirs("recordings", exist_ok=True)

    audio_path = None
    video_path = None

    if audio_file:
        audio_path = os.path.join("recordings", f"{session_id}_{question_id}_audio.wav")
        with open(audio_path, "wb") as f:
            shutil.copyfileobj(audio_file.file, f)

    if video_file:
        video_path = os.path.join("recordings", f"{session_id}_{question_id}_video.mp4")
        with open(video_path, "wb") as f:
            shutil.copyfileobj(video_file.file, f)

    response_data = {
        "response_id": response_id,
        "session_id": session_id,
        "question_id": question_id,
        "audio_path": audio_path,
        "video_path": video_path,
        "transcript": transcript,
        "created_at": datetime.now(),
        "analysis_status": "pending",
    }
    question_responses[response_id] = response_data
    return {"message": "Response submitted", "response_id": response_id}

@router.get("/{session_id}/responses")
async def get_session_responses(session_id: str):
    if session_id not in interview_sessions:
        _ensure_session_minimal(session_id)
    session_responses = [r for r in question_responses.values() if r["session_id"] == session_id]
    return {"session_id": session_id, "responses": session_responses}

@router.delete("/{session_id}")
async def delete_interview_session(session_id: str):
    interview_sessions.pop(session_id, None)
    to_del = [rid for rid, r in question_responses.items() if r["session_id"] == session_id]
    for rid in to_del:
        question_responses.pop(rid, None)
    return {"message": "Session deleted successfully"}

@router.get("/")
async def list_interview_sessions():
    return {"sessions": list(interview_sessions.values())}
