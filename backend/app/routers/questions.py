# backend/app/routers/questions.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os

router = APIRouter()

class GenerateRequest(BaseModel):
    job_description: str
    num_questions: int = 1
    difficulty_level: Optional[str] = "medium"
    question_types: List[str] = []

@router.post("/generate")
async def generate_questions(body: GenerateRequest):
    jd = (body.job_description or "").strip()
    if not jd:
        # still return something useful, but mark it as fallback
        return {"ok": True, "questions": [{"question_text": "Tell me about yourself."}]}

    # Try Gemini if key present
    api_key = os.getenv("GEMINI_API_KEY")
    use_gemini = os.getenv("USE_GEMINI", "true").lower() == "true" and api_key
    if use_gemini:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            prompt = (
                "You are an interview question generator. "
                f"Job Description:\n{jd}\n\n"
                f"Return {body.num_questions} concise interview questions "
                f"mixing types: {', '.join(body.question_types) or 'general'}."
            )
            model = genai.GenerativeModel("gemini-1.5-flash")
            resp = model.generate_content(prompt)
            text = (resp.text or "").strip()
            # naive split – you can improve formatting later
            lines = [ln.strip("-• ").strip() for ln in text.split("\n") if ln.strip()]
            qs = [l for l in lines if len(l) > 10][: max(1, body.num_questions)]
            if not qs:
                qs = ["Tell me about yourself."]
            return {"ok": True, "questions": [{"question_text": q} for q in qs]}
        except Exception:
            # fall through to template
            pass

    # Fallback templates if Gemini fails
    fallback = [
        "Walk me through a recent project you led. What was the impact?",
        "Tell me about a time you disagreed with a decision and what you did.",
        "Describe a tough technical problem you solved and how."
    ]
    return {"ok": True, "questions": [{"question_text": q} for q in fallback[: body.num_questions]]}
