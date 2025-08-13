from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime
import json

router = APIRouter()

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

# In-memory storage (replace with actual database)
interview_sessions = {}
question_responses = {}

@router.post("/create", response_model=InterviewSessionResponse)
async def create_interview_session(session_data: InterviewSessionCreate):
    """Create a new interview session"""
    try:
        session_id = str(uuid.uuid4())
        num_questions = session_data.total_time // session_data.minutes_per_question
        
        session = {
            "session_id": session_id,
            "name": session_data.name,
            "job_description": session_data.job_description,
            "minutes_per_question": session_data.minutes_per_question,
            "total_time": session_data.total_time,
            "num_questions": num_questions,
            "created_at": datetime.now(),
            "status": "created"
        }
        
        interview_sessions[session_id] = session
        
        return InterviewSessionResponse(**session)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating session: {str(e)}")

@router.get("/{session_id}", response_model=InterviewSessionResponse)
async def get_interview_session(session_id: str):
    """Get interview session details"""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return InterviewSessionResponse(**interview_sessions[session_id])

@router.post("/{session_id}/start")
async def start_interview_session(session_id: str):
    """Start an interview session"""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    interview_sessions[session_id]["status"] = "in_progress"
    interview_sessions[session_id]["started_at"] = datetime.now()
    
    return {"message": "Interview session started", "session_id": session_id}

@router.post("/{session_id}/complete")
async def complete_interview_session(session_id: str):
    """Complete an interview session"""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    interview_sessions[session_id]["status"] = "completed"
    interview_sessions[session_id]["completed_at"] = datetime.now()
    
    return {"message": "Interview session completed", "session_id": session_id}

@router.post("/{session_id}/response")
async def submit_response(
    session_id: str,
    question_id: str,
    audio_file: Optional[UploadFile] = File(None),
    video_file: Optional[UploadFile] = File(None),
    transcript: Optional[str] = None
):
    """Submit a response for a question"""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    response_id = str(uuid.uuid4())
    
    # Save uploaded files (implement actual file storage)
    audio_path = None
    video_path = None
    
    if audio_file:
        audio_path = f"recordings/{session_id}_{question_id}_audio.wav"
        # Save audio file logic here
    
    if video_file:
        video_path = f"recordings/{session_id}_{question_id}_video.mp4"
        # Save video file logic here
    
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
    """Get all responses for a session"""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_responses = [
        response for response in question_responses.values()
        if response["session_id"] == session_id
    ]
    
    return {"session_id": session_id, "responses": session_responses}

@router.delete("/{session_id}")
async def delete_interview_session(session_id: str):
    """Delete an interview session"""
    if session_id not in interview_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del interview_sessions[session_id]
    
    # Delete associated responses
    responses_to_delete = [
        response_id for response_id, response in question_responses.items()
        if response["session_id"] == session_id
    ]
    
    for response_id in responses_to_delete:
        del question_responses[response_id]
    
    return {"message": "Session deleted successfully"}

@router.get("/")
async def list_interview_sessions():
    """List all interview sessions"""
    return {"sessions": list(interview_sessions.values())}
