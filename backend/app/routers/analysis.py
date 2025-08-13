from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import logging
from datetime import datetime

# Import the speech service
from app.services.speech_service import SpeechAnalysisService

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize speech service
speech_service = SpeechAnalysisService()

class AnalysisRequest(BaseModel):
    session_id: str
    data_type: str  # 'audio', 'video', 'combined'
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

# In-memory storage for analysis results
analysis_results = {}

@router.post("/audio", response_model=AnalysisResponse)
async def analyze_audio(request: AnalysisRequest):
    """Analyze audio data for speech quality, filler words, etc."""
    try:
        # Mock speech analysis (replace with actual implementation)
        speech_results = {
            "transcript": "This is a sample transcript of the user's response...",
            "filler_words": {
                "um": 2,
                "uh": 1,
                "like": 3
            },
            "speaking_pace": "normal",  # slow, normal, fast
            "clarity_score": 85,
            "volume_level": "appropriate",
            "pronunciation_issues": []
        }
        
        analysis_id = f"audio_{request.session_id}_{len(analysis_results)}"
        
        response = AnalysisResponse(
            analysis_id=analysis_id,
            session_id=request.session_id,
            analysis_type="audio",
            results=speech_results,
            confidence_score=0.92,
            timestamp=str(datetime.now())
        )
        
        analysis_results[analysis_id] = response.dict()
        
        return response
    
    except Exception as e:
        logger.error(f"Audio analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {str(e)}")

@router.post("/speech-analysis")
async def analyze_speech_file(audio: UploadFile = File(...), session_id: str = Form(...)):
    """Analyze uploaded audio file using real Whisper AI speech service"""
    try:
        logger.info(f"Received audio file for speech analysis: {audio.filename}, session: {session_id}")
        
        # Initialize speech service if not already done
        if not hasattr(speech_service, 'initialized') or not speech_service.initialized:
            await speech_service.initialize()
            speech_service.initialized = True
        
        # Read audio file data
        audio_data = await audio.read()
        
        # Use the real speech service for analysis
        analysis_result = await speech_service.analyze_audio_chunk(audio_data, session_id)
        
        logger.info(f"Speech analysis completed for session {session_id}")
        
        return {
            "status": "success",
            "session_id": session_id,
            "analysis": analysis_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Speech analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Speech analysis failed: {str(e)}")

@router.post("/video", response_model=AnalysisResponse)
async def analyze_video(request: AnalysisRequest):
    """Analyze video data for posture, gestures, eye contact, etc."""
    try:
        # Mock video analysis (replace with actual implementation)
        video_results = {
            "posture_score": 78,
            "posture_classification": "good",  # poor, fair, good, excellent
            "eye_contact_score": 82,
            "gesture_analysis": {
                "appropriate_gestures": 85,
                "fidgeting_detected": False,
                "hand_position": "appropriate"
            },
            "facial_expression": {
                "confidence_level": "moderate",
                "engagement_score": 88,
                "emotion_detected": "neutral"
            },
            "movement_analysis": {
                "stability": "stable",
                "excessive_movement": False
            }
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
    """Get all analysis results for a session"""
    session_analyses = [
        analysis for analysis in analysis_results.values()
        if analysis["session_id"] == session_id
    ]
    
    if not session_analyses:
        raise HTTPException(status_code=404, detail="No analysis found for session")
    
    return {"session_id": session_id, "analyses": session_analyses}

@router.get("/report/{session_id}", response_model=FeedbackReport)
async def generate_feedback_report(session_id: str):
    """Generate comprehensive feedback report for a session"""
    try:
        # Get all analyses for the session
        session_analyses = [
            analysis for analysis in analysis_results.values()
            if analysis["session_id"] == session_id
        ]
        
        if not session_analyses:
            raise HTTPException(status_code=404, detail="No analysis data found for session")
        
        # Aggregate analysis results
        audio_analyses = [a for a in session_analyses if a["analysis_type"] == "audio"]
        video_analyses = [a for a in session_analyses if a["analysis_type"] == "video"]
        
        # Calculate overall scores
        speech_score = 85 if audio_analyses else 0
        body_language_score = 78 if video_analyses else 0
        overall_score = int((speech_score + body_language_score) / 2)
        
        # Generate recommendations
        recommendations = []
        if speech_score < 80:
            recommendations.append("Practice reducing filler words in your speech")
        if body_language_score < 80:
            recommendations.append("Work on maintaining better posture during interviews")
        
        recommendations.extend([
            "Maintain eye contact with the camera",
            "Practice your responses to common interview questions",
            "Use confident body language and gestures"
        ])
        
        # Detailed metrics
        detailed_metrics = {
            "total_questions": len(audio_analyses),
            "average_response_length": 45,  # seconds
            "total_filler_words": sum([
                sum(a["results"].get("filler_words", {}).values()) 
                for a in audio_analyses
            ]),
            "posture_consistency": 78,
            "engagement_level": 85
        }
        
        # Mock speech analysis summary
        speech_analysis = {
            "overall_clarity": speech_score,
            "speaking_pace": "normal",
            "filler_word_frequency": "low",
            "pronunciation_score": 90,
            "voice_confidence": 82
        }
        
        # Mock body language analysis summary
        body_language_analysis = {
            "posture_score": body_language_score,
            "eye_contact_score": 82,
            "gesture_appropriateness": 85,
            "facial_expression_score": 88,
            "overall_presence": 80
        }
        
        report = FeedbackReport(
            session_id=session_id,
            overall_score=overall_score,
            speech_analysis=speech_analysis,
            body_language_analysis=body_language_analysis,
            recommendations=recommendations,
            detailed_metrics=detailed_metrics
        )
        
        return report
    
    except Exception as e:
        logger.error(f"Report generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@router.get("/metrics/{session_id}")
async def get_session_metrics(session_id: str):
    """Get detailed metrics for a session"""
    session_analyses = [
        analysis for analysis in analysis_results.values()
        if analysis["session_id"] == session_id
    ]
    
    if not session_analyses:
        raise HTTPException(status_code=404, detail="No analysis found for session")
    
    # Calculate metrics
    metrics = {
        "total_analyses": len(session_analyses),
        "audio_analyses": len([a for a in session_analyses if a["analysis_type"] == "audio"]),
        "video_analyses": len([a for a in session_analyses if a["analysis_type"] == "video"]),
        "average_confidence": sum([a["confidence_score"] for a in session_analyses]) / len(session_analyses),
        "latest_analysis": max(session_analyses, key=lambda x: x["timestamp"])["timestamp"]
    }
    
    return {"session_id": session_id, "metrics": metrics}
