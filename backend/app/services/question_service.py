import os, json, logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
except Exception:
    genai = None

PROMPT = """You are an expert interview question generator.
Given a job description, produce {num} concise interview questions tailored to the role.
Target difficulty: {difficulty}. Include a good mix of: {types}.

Return ONLY JSON in this exact schema:
{{
  "questions": [
    {{
      "question_text": "string",
      "type": "behavioral|technical|situational|general",
      "hint": "short coaching hint (optional)"
    }}
  ]
}}
Job Description:
---
{jd}
---
"""

class QuestionGeneratorService:
    def __init__(self):
        self.use_gemini = os.getenv("USE_GEMINI", "true").lower() in ("1","true","yes")
        self.api_key = os.getenv("GEMINI_API_KEY")

        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.initialized = False
        self.model = None

    async def initialize(self):
        if not self.use_gemini or not self.api_key or genai is None:
            logger.warning("Gemini disabled or not available. Using fallback questions.")
            self.initialized = True
            return

        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            self.initialized = True
            logger.info("Gemini question generator initialized.")
        except Exception as e:
            logger.error(f"Gemini init failed: {e}")
            self.model = None
            self.initialized = True

    async def cleanup(self):
        pass

    def _fallback(self, n: int) -> List[Dict]:
        base = [
            {"question_text":"Tell me about yourself.","type":"general","hint":"45–90s: past → present → future."},
            {"question_text":"Describe a project you’re proud of and the concrete impact it had.","type":"behavioral","hint":"Use STAR, include metrics."},
            {"question_text":"Walk me through a tough technical problem you solved recently.","type":"technical","hint":"State the problem, options, trade-offs, result."},
            {"question_text":"Tell me about a time you handled conflicting priorities.","type":"situational","hint":"Escalation paths, stakeholders, outcome."},
        ]
        return base[:max(1, n)]

    async def generate_questions(
        self,
        job_description: str,
        num_questions: int = 1,
        difficulty_level: str = "medium",
        question_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        question_types = question_types or ["behavioral","technical","situational","general"]

        if not self.use_gemini or not self.api_key or self.model is None:
            return self._fallback(num_questions)

        try:
            prompt = PROMPT.format(
                jd=job_description.strip(),
                num=num_questions,
                difficulty=difficulty_level,
                types=", ".join(question_types),
            )
            resp = self.model.generate_content(prompt)
            text = resp.text or ""
            # Strip code fences if any, then parse JSON
            text = text.strip().strip("`").strip()
            data = json.loads(text)
            items = data.get("questions", [])
            cleaned = []
            for it in items:
                q = it.get("question_text") or it.get("question") or ""
                if not q: continue
                cleaned.append({
                    "question_text": q.strip(),
                    "type": it.get("type") or "general",
                    "hint": (it.get("hint") or "Use STAR: Situation, Task, Action, Result.").strip()
                })
            return cleaned[:max(1, num_questions)] or self._fallback(num_questions)
        except Exception as e:
            logger.warning(f"Gemini generation failed, fallback used: {e}")
            return self._fallback(num_questions)
