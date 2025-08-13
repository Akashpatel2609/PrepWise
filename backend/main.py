from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Import routers
from app.routers import interview, analysis, questions

# Import services
from app.services.speech_service import SpeechAnalysisService
from app.services.video_service import VideoAnalysisService
from app.services.question_service import QuestionGeneratorService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PrepWise API",
    description="Mock Interview Platform Backend API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "http://127.0.0.1:5000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
speech_service = SpeechAnalysisService()
video_service = VideoAnalysisService()
question_service = QuestionGeneratorService()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_personal_message(self, message: str, session_id: str):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(message)

    async def send_analysis_data(self, data: dict, session_id: str):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_text(json.dumps(data))

manager = ConnectionManager()

# Include routers
app.include_router(interview.router, prefix="/api/interview", tags=["interview"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(questions.router, prefix="/api/questions", tags=["questions"])

@app.get("/")
async def root():
    return {"message": "PrepWise API is running", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "speech_analysis": "active",
            "video_analysis": "active",
            "question_generator": "active"
        }
    }

@app.websocket("/ws/interview/{session_id}")
async def websocket_interview_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            # Receive data from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Process based on message type
            if message["type"] == "audio_data":
                # Process audio for speech analysis
                analysis_result = await speech_service.analyze_audio_chunk(
                    message["data"], session_id
                )
                await manager.send_analysis_data({
                    "type": "speech_analysis",
                    "data": analysis_result
                }, session_id)
                
            elif message["type"] == "video_frame":
                # Process video frame for posture analysis
                analysis_result = await video_service.analyze_frame(
                    message["data"], session_id
                )
                await manager.send_analysis_data({
                    "type": "video_analysis", 
                    "data": analysis_result
                }, session_id)
                
            elif message["type"] == "audio_level":
                # Simple audio level monitoring
                await manager.send_analysis_data({
                    "type": "audio_monitoring",
                    "data": {"level": message["data"]["level"]}
                }, session_id)

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        logger.info(f"Client {session_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {str(e)}")
        manager.disconnect(session_id)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error", "detail": str(exc)}
    )

# Background task for periodic analysis
async def background_analysis_task():
    """Background task to perform periodic analysis and cleanup"""
    while True:
        try:
            # Perform any periodic maintenance here
            logger.info("Running background analysis task")
            await asyncio.sleep(30)  # Run every 30 seconds
        except Exception as e:
            logger.error(f"Background task error: {str(e)}")
            await asyncio.sleep(60)  # Wait longer if there's an error

@app.on_event("startup")
async def startup_event():
    logger.info("PrepWise API starting up...")
    
    # Initialize services
    await speech_service.initialize()
    await video_service.initialize()
    await question_service.initialize()
    
    # Start background tasks
    asyncio.create_task(background_analysis_task())
    
    logger.info("PrepWise API startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("PrepWise API shutting down...")
    
    # Cleanup services
    await speech_service.cleanup()
    await video_service.cleanup()
    
    logger.info("PrepWise API shutdown complete")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
