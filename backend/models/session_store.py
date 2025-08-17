# app/models/session_store.py
from datetime import datetime
from typing import Dict, Optional, Any, List

# Super-simple in-memory store (replace with DB later)
SESSIONS: Dict[str, dict] = {}

def ensure_session(session_id: str, *, job_description: Optional[str] = None) -> dict:
    """
    Ensure a session object exists; create if missing.
    """
    s = SESSIONS.get(session_id)
    if not s:
        s = {
            "session_id": session_id,
            "job_description": job_description or "",
            "created_at": datetime.utcnow().isoformat(),
            "questions": [],      # list[{"id","text","type","hint"}]
            "transcripts": [],    # list[{"question","responseText","duration","confidence","timestamp"}]
            "meta": {},
        }
        SESSIONS[session_id] = s
    else:
        # Fill in JD if newly provided
        if job_description and not s.get("job_description"):
            s["job_description"] = job_description
    return s

def add_question(session_id: str, question: dict) -> None:
    s = ensure_session(session_id)
    s["questions"].append(question)

def add_transcript(session_id: str, payload: dict) -> None:
    s = ensure_session(session_id)
    s["transcripts"].append(payload)

def get_questions(session_id: str) -> List[dict]:
    return ensure_session(session_id).get("questions", [])

def get_transcripts(session_id: str) -> List[dict]:
    return ensure_session(session_id).get("transcripts", [])
