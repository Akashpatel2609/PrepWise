# app/routers/questions.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging, os, random

from app.models.session_store import ensure_session, add_question, get_questions

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------- Request/Response models ----------
class GenerateRequest(BaseModel):
    session_id: str
    job_description: str
    num_questions: int = 1
    difficulty_level: Optional[str] = "medium"
    question_types: Optional[List[str]] = ["behavioral", "technical", "situational"]

class GeneratedQuestion(BaseModel):
    ok: bool = True
    session_id: str
    question: str
    hint: Optional[str] = ""
    type: Optional[str] = "behavioral"
    source: str = "fallback"
    index: int

# ---------- Local fallback bank ----------
FALLBACK = {
    "general": [
        ("Tell me about yourself.", "Give a concise overview and connect it to this role."),
        ("Describe a project you’re proud of and the concrete impact it had.",
         "Use STAR: Situation, Task, Action, Result."),
    ],
    "frontend": [
        ("How would you improve performance in a large React view that feels janky?",
         "Discuss profiling, memoization, virtualization, and lazy-loading."),
    ],
    "backend": [
        ("Design a resilient API endpoint that handles traffic spikes gracefully.",
         "Talk through rate-limiting, retries, backoff, and caching."),
    ],
    "data": [
        ("Walk me through your process to clean a messy dataset and validate correctness.",
         "Mention missing values, outliers, validation, and reproducibility."),
    ],
    "ml": [
        ("Design an end-to-end ML pipeline and explain how you’d monitor drift.",
         "Cover data/versioning, training, eval, serving, and monitoring."),
    ],
}

def _pick_fallback(job_description: str) -> tuple[str, str, str]:
    jd = (job_description or "").lower()
    bucket = "general"
    if any(k in jd for k in ("react","frontend","ui","css","typescript")):
        bucket = "frontend"
    elif any(k in jd for k in ("api","backend","django","flask","node","microservice")):
        bucket = "backend"
    elif any(k in jd for k in ("data analyst","sql","tableau","analytics")):
        bucket = "data"
    elif any(k in jd for k in ("ml","machine learning","pytorch","tensorflow")):
        bucket = "ml"
    q,h = random.choice(FALLBACK[bucket])
    qtype = "technical" if bucket in ("frontend","backend","data","ml") else "behavioral"
    return q,h,qtype

def _try_gemini(job_description: str) -> Optional[str]:
    """
    Returns a single question string from Gemini, or None on failure/unavailable.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        model = genai.GenerativeModel(model_name)
        prompt = (
            "You are an interview coach. Create ONE concise, specific, role-relevant interview "
            "question for this job description. Return ONLY the question text, nothing else.\n\n"
            f"Job description:\n{job_description}\n"
        )
        # Synchronous call is fine here; if you prefer, wrap in asyncio.to_thread(...)
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
        # Clean possible quotes or markdown bullets
        text = text.strip().strip("-•").strip()
        return text or None
    except Exception as e:
        logger.warning("Gemini generation failed: %s", e)
        return None

@router.post("/generate", response_model=GeneratedQuestion)
async def generate(req: GenerateRequest):
    """
    Generate a single interview question. Prefers Gemini if GEMINI_API_KEY is set,
    otherwise falls back to curated bank.
    """
    try:
        session = ensure_session(req.session_id, job_description=req.job_description)
        # First try Gemini
        q_text = _try_gemini(req.job_description)
        source = "gemini" if q_text else "fallback"

        if not q_text:
            q_text, hint, qtype = _pick_fallback(req.job_description)
        else:
            # Make a lightweight hint for Gemini-generated question
            hint = "Answer with STAR: Situation, Task, Action, Result."
            qtype = "behavioral" if "experience" in q_text.lower() else "technical"

        idx = len(get_questions(req.session_id)) + 1
        q = {"id": f"q_{idx}", "text": q_text, "type": qtype, "hint": hint}
        add_question(req.session_id, q)

        return GeneratedQuestion(
            ok=True,
            session_id=req.session_id,
            question=q_text,
            hint=hint,
            type=qtype,
            source=source,
            index=idx,
        )
    except Exception as e:
        logger.exception("Question generation error")
        raise HTTPException(status_code=500, detail=f"Failed to generate question: {e}")

@router.get("/types")
async def get_question_types():
    return {
        "types": ["behavioral", "technical", "situational"],
        "descriptions": {
            "behavioral": "Past experiences and behavior",
            "technical": "Skills and knowledge",
            "situational": "Hypothetical scenarios",
        },
    }
