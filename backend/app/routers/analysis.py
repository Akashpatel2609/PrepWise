# app/routers/analysis.py
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import List, Optional, Dict
import logging, re, json
from datetime import datetime
from fastapi.responses import JSONResponse
from collections import defaultdict
import tempfile, subprocess, os, contextlib, wave

# --- Optional Gemini for coaching ---
USE_GEMINI = (os.getenv("USE_GEMINI", "false").lower() == "true")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
gemini_model = None
if USE_GEMINI and GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception:
        gemini_model = None

# Optional session meta import (job description, etc.)
try:
    from app.models.session_store import SESSIONS  # type: ignore
except Exception:
    SESSIONS = {}  # graceful fallback if not present

from app.services.speech_service import SpeechAnalysisService
from app.services.video_service import VideoAnalysisService

def _ffmpeg_decode_to_wav_16k(src_path: str, dst_path: str) -> None:
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

def _count_fillers(text: str) -> Dict[str, int]:
    words = [w.strip(".,?!;:()[]\"'").lower() for w in (text or "").split()]
    counts = {"um": 0, "uh": 0, "like": 0}
    for w in words:
        if w in counts: counts[w] += 1
    counts["total"] = counts["um"] + counts["uh"] + counts["like"]
    return counts

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
video_service = VideoAnalysisService()

# Stores
analysis_results: Dict[str, dict] = {}
session_summaries = defaultdict(lambda: {
    "chunks": [],            # [{question_number, text, words, duration, confidence, timestamp}]
    "questions": {},         # {qnum: question_text}
    "total_words": 0,
    "total_duration": 0.0,
    "filler": {"um": 0, "uh": 0, "like": 0},
    "rates": [], "clarities": [], "confidences": [],
})
posture_aggregate = defaultdict(lambda: defaultdict(int))  # {session_id: {posture_label: count}}

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

# ---------------- SPEECH ----------------
@router.post("/speech-analysis")
async def analyze_speech_file(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    question_number: Optional[int] = Form(None),
    mime: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
    question_text: Optional[str] = Form(None),
):
    tmp_in = tmp_wav = None
    try:
        ct = (mime or audio.content_type or "").lower()

        if not getattr(speech_service, "initialized", False):
            await speech_service.initialize()
            speech_service.initialized = True

        raw_bytes = await audio.read()

        if   "wav"  in ct: suffix = ".wav"
        elif "ogg"  in ct: suffix = ".ogg"
        elif "webm" in ct: suffix = ".webm"
        elif "mp4" in ct or "mpeg" in ct or "m4a" in ct: suffix = ".m4a"
        else: suffix = os.path.splitext(audio.filename or "")[-1] or ".bin"

        tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_in.write(raw_bytes); tmp_in.flush(); tmp_in.close()
        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav"); tmp_wav.close()

        computed_duration = 0.0
        try:
            _ffmpeg_decode_to_wav_16k(tmp_in.name, tmp_wav.name)
            # read wav duration
            try:
                with contextlib.closing(wave.open(tmp_wav.name, "rb")) as wf:
                    frames = wf.getnframes()
                    fr = wf.getframerate() or 16000
                    computed_duration = frames / float(fr)
            except Exception:
                computed_duration = 0.0
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
                    "text": "", "analysis": {"transcript": "", "filler_count": 0, "confidence": 0.0, "duration": 0.0},
                }, status_code=200)

        transcript_text = (analysis_result.get("transcript_chunk")
                           or analysis_result.get("text")
                           or analysis_result.get("transcript")
                           or "").strip()

        perf = analysis_result.get("performance_metrics", {}) or {}
        aq   = analysis_result.get("audio_quality", {}) or {}
        fw   = analysis_result.get("filler_words", {}) or {}
        breakdown = fw.get("breakdown", {}) or {}

        filler_count = int(breakdown.get("um", 0) or 0) + int(breakdown.get("uh", 0) or 0) + int(breakdown.get("like", 0) or 0)
        if filler_count == 0 and transcript_text:
            breakdown = {k: 0 for k in ("um","uh","like")}
            auto = _count_fillers(transcript_text)
            filler_count = auto["total"]
            for k in ("um","uh","like"):
                breakdown[k] = auto.get(k, 0)

        clarity_score = int(aq.get("clarity_score", 0) or 0)
        speaking_rate = aq.get("speaking_rate", 0) or 0
        volume_level  = aq.get("volume_level", "") or "unknown"
        duration      = float(analysis_result.get("duration", 0.0) or 0.0)
        if duration <= 0.0 and computed_duration > 0.0:
            duration = computed_duration
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

        # Persist into session summary for final report
        words = len([w for w in (transcript_text or "").split() if w.strip()])
        s = session_summaries[session_id]
        if isinstance(question_number, int) and question_text:
            s["questions"][int(question_number)] = question_text
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

        # Interview page: keep response minimal (we'll show details on Feedback)
        return {
            "ok": True, "status": "success",
            "session_id": session_id, "question_number": question_number,
            "text": "",
            "analysis": {"transcript": "", "filler_count": int(filler_count), "confidence": confidence, "duration": duration},
            "timestamp": record["timestamp"]
        }

    except Exception as e:
        logger.error(f"Speech analysis error: {str(e)}")
        return JSONResponse({
            "ok": False, "error": "transcription_failed", "detail": str(e),
            "session_id": session_id, "question_number": question_number,
            "text": "", "analysis": {"transcript": "", "filler_count": 0, "confidence": 0.0, "duration": 0.0},
        }, status_code=200)
    finally:
        for p in ((tmp_in.name if tmp_in else None), (tmp_wav.name if tmp_wav else None)):
            if p:
                try: os.unlink(p)
                except: pass

# ---------------- VIDEO (frame-by-frame) ----------------
@router.post("/video-frame")
async def analyze_video_frame(
    session_id: str = Form(...),
    frame: UploadFile = File(...),
):
    # Lazy init
    if not getattr(video_service, "initialized", False):
        await video_service.initialize()
        video_service.initialized = True

    try:
        img_bytes = await frame.read()
        result = await video_service.analyze_frame(img_bytes, session_id)  # expects dict
        # Normalize possible keys
        label = (
            result.get("posture_classification")
            or result.get("posture_class")
            or result.get("label")
            or "Neutral"
        )
        posture_aggregate[session_id][label] += 1
        return {"ok": True, "label": label}
    except Exception as e:
        logger.error(f"Video frame analysis failed: {e}")
        return {"ok": False, "error": "video_analysis_failed", "detail": str(e)}

# ---------------- REPORT (used by Feedback page) ----------------
def _heuristic_feedback(q_text: str, ans: str, job_desc: str) -> Dict[str, List[str]]:
    issues, improvements = [], []

    # Length heuristics
    word_count = len(ans.split())
    if word_count < 60:
        issues.append("Answer is brief—aim for ~45–90 seconds with concrete detail.")
    if word_count > 280:
        issues.append("Answer is long—tighten to the core story and impact.")

    # Metrics / impact
    if not re.search(r"(\d+%|\$\d+|\d+\s?(ms|s|sec|minutes?|hours?)|users?|latency|throughput|revenue|cost|error rate|NPS)", ans, re.I):
        issues.append("No measurable impact—add numbers (%, $, time, users) to quantify results.")

    # STAR coverage
    if not re.search(r"\b(situation|context|background)\b", ans, re.I):
        improvements.append("Add a 1–2 sentence Situation for context.")
    if not re.search(r"\b(task|goal|objective)\b", ans, re.I):
        improvements.append("State the Task/Goal explicitly so the listener knows the target.")
    if not re.search(r"\b(action|implemented|built|designed|led|debugged|optimized)\b", ans, re.I):
        improvements.append("Describe your Actions with strong verbs—what *you* did.")
    if not re.search(r"\b(result|impact|outcome|improv|reduce|increase)\b", ans, re.I):
        improvements.append("Close with Results/Impact and a specific metric.")

    # Relevance to JD
    jd = (job_desc or "").lower()
    buckets = {
        "frontend": r"(react|typescript|css|ui|accessibility|bundle|webpack|vite|component)",
        "backend": r"(api|microservice|scal(e|ing)|database|queue|kafka|redis|auth|caching)",
        "data": r"(sql|etl|tableau|bi|analytics|warehouse|snowflake|bigquery|look(er)?)",
        "ml": r"(ml|machine learning|model|pytorch|tensorflow|sklearn|inference|drift)",
    }
    bucket_hit = None
    for b, rx in buckets.items():
        if re.search(rx, jd): bucket_hit = (b, rx); break
    if bucket_hit:
        b, rx = bucket_hit
        if not re.search(rx, ans, re.I):
            issues.append("Answer doesn’t tie clearly to the role—reference role-relevant tools/techniques.")

    # Generic coaching
    improvements += [
        "Start with a 1-sentence headline of the achievement before details.",
        "Weave in trade-offs and your decision rationale briefly.",
        "End with what you learned or how you’d do it better next time.",
    ]
    return {"issues": issues, "improvements": improvements}

@router.get("/report/{session_id}")
async def generate_feedback_report(session_id: str):
    try:
        session_analyses = [a for a in analysis_results.values() if a["session_id"] == session_id]
        s = session_summaries.get(session_id)
        if not s and not session_analyses:
            raise HTTPException(status_code=404, detail="No analysis data found for session")

        if not s:
            s = {
                "chunks": [], "questions": {}, "total_words": 0, "total_duration": 0.0,
                "filler": {"um":0,"uh":0,"like":0}, "rates": [], "clarities": [], "confidences": []
            }

        job_desc = ""
        try:
            job_desc = SESSIONS.get(session_id, {}).get("job_description", "")
        except Exception:
            job_desc = ""

        # Group by question
        from collections import defaultdict as _dd
        by_q = _dd(list)
        for ch in s["chunks"]:
            qn = int(ch.get("question_number") or 1)
            by_q[qn].append(ch)

        transcript = []
        for qn in sorted(by_q.keys()):
            items = by_q[qn]
            text = " ".join(i.get("text", "") for i in items if i.get("text"))
            words = sum(i.get("words", 0) for i in items) or len(text.split())
            duration = sum(i.get("duration", 0.0) for i in items)
            confidence = (sum(i.get("confidence", 0.0) for i in items) / max(1, len(items)))
            ts = items[0].get("timestamp", "") if items else ""
            if words < 5 and duration < 1.0 and len(text.strip()) < 12:
                continue
            transcript.append({
                "question_number": qn,
                "question": s["questions"].get(qn, f"Response to Question {qn}"),
                "response": text,
                "timestamp": ts.split("T")[-1][:8] if ts else "",
                "duration": duration,
                "confidence": confidence
            })

        avg_rate    = (sum(s["rates"]) / len(s["rates"])) if s["rates"] else 0.0
        avg_clarity = (sum(s["clarities"]) / len(s["clarities"])) if s["clarities"] else 0.0
        avg_conf    = (sum(s["confidences"]) / len(s["confidences"])) if s["confidences"] else 0.5

        speech_score        = int(min(100, max(0, (avg_clarity or 70))))
        body_language_score = 78  # will be recalculated if we have posture data
        overall_score       = int((speech_score + body_language_score) / 2)

        response_time_score = 80 if _speaking_rate_label(avg_rate) == "Good pace" else (40 if _speaking_rate_label(avg_rate) == "Too slow" else 60)
        confidence_score    = int(round(avg_conf * 100))
        content_score       = 70

        # Per-question coaching (heuristics + Gemini JSON if available)
        per_q_feedback = []
        for item in transcript:
            q_text = item["question"]
            ans = item["response"]
            f = _count_fillers(ans)

            base = _heuristic_feedback(q_text, ans, job_desc)
            issues = base["issues"]
            improvements = base["improvements"]
            model_answer = ""

            if gemini_model and ans.strip():
                try:
                    prompt = (
                        "Return strict JSON with keys: issues (string[]), improvements (string[]), model_answer (string). "
                        "Be specific to the question and concise.\n\n"
                        f"Job Description:\n{job_desc}\n\n"
                        f"Question:\n{q_text}\n\n"
                        f"Candidate Answer:\n{ans}\n\n"
                        "JSON only, no prose."
                    )
                    resp = gemini_model.generate_content(prompt)
                    txt = getattr(resp, "text", "").strip()
                    data = json.loads(txt)
                    # Merge/override sensibly
                    if isinstance(data.get("issues"), list):
                        issues = list(dict.fromkeys(issues + [i for i in data["issues"] if isinstance(i, str) and i.strip()]))
                    if isinstance(data.get("improvements"), list):
                        improvements = list(dict.fromkeys(improvements + [i for i in data["improvements"] if isinstance(i, str) and i.strip()]))
                    if isinstance(data.get("model_answer"), str):
                        model_answer = data["model_answer"].strip()
                except Exception:
                    # fallback: keep heuristic + maybe short improved sample
                    pass

            per_q_feedback.append({
                "question_number": item["question_number"],
                "question": q_text,
                "transcript": ans,
                "filler_words": f,
                "issues": issues,
                "improvements": improvements,
                "model_answer": model_answer
            })

        # Posture distribution: prefer live aggregate if present
        posture_dist = dict(posture_aggregate.get(session_id, {}))
        if not posture_dist:
            posture_dist = {"Good Posture": 3, "Confident Expression": 2, "Neutral": 1, "Slouching": 1}

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
            "filler_aggregate": s["filler"],
            "per_question_feedback": per_q_feedback,
            "posture_distribution": posture_dist
        }
        return payload
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")
