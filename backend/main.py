# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn, json, asyncio, logging
from datetime import datetime
from typing import Dict
from dotenv import load_dotenv

# Routers
from app.routers import interview, analysis, questions

# Services
from app.services.speech_service import SpeechAnalysisService
from app.services.video_service import VideoAnalysisService
from app.services.question_service import QuestionGeneratorService

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("app.routers.analysis").setLevel(logging.DEBUG)

# Create app FIRST
app = FastAPI(title="PrepWise API", description="Mock Interview Platform Backend API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000","http://127.0.0.1:5000",
        "http://localhost:5173","http://127.0.0.1:5173",
        "http://localhost:5174","http://127.0.0.1:5174",
    ],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# Instantiate services ONCE
speech_service  = SpeechAnalysisService()
video_service   = VideoAnalysisService()
question_service= QuestionGeneratorService()

# Attach to app.state so routers can access if needed
app.state.speech_service   = speech_service
app.state.video_service    = video_service
app.state.question_service = question_service

# Routers
app.include_router(interview.router, prefix="/api/interview", tags=["interview"])
app.include_router(analysis.router,  prefix="/api/analysis",  tags=["analysis"])
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
            "question_generator": "active",
        },
    }

class ConnectionManager:
    def __init__(self): self.active_connections: Dict[str, WebSocket] = {}
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept(); self.active_connections[session_id] = websocket
        logger.info("WebSocket connected for session: %s", session_id)
    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)
        logger.info("WebSocket disconnected for session: %s", session_id)
    async def send_analysis_data(self, data: dict, session_id: str):
        ws = self.active_connections.get(session_id)
        if ws: await ws.send_text(json.dumps(data))

manager = ConnectionManager()

@app.websocket("/ws/interview/{session_id}")
async def websocket_interview_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    try:
        while True:
            msg = json.loads(await websocket.receive_text())
            t = msg.get("type")
            if t == "audio_data":
                result = await speech_service.analyze_audio_chunk(msg["data"], session_id)
                await manager.send_analysis_data({"type": "speech_analysis", "data": result}, session_id)
            elif t == "video_frame":
                result = await video_service.analyze_frame(msg["data"], session_id)
                await manager.send_analysis_data({"type": "video_analysis", "data": result}, session_id)
            elif t == "audio_level":
                await manager.send_analysis_data({"type": "audio_monitoring", "data": {"level": msg["data"]["level"]}}, session_id)
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error("WebSocket error (%s): %s", session_id, e)
        manager.disconnect(session_id)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error("Global exception: %s", exc)
    return JSONResponse(status_code=500, content={"message": "Internal server error", "detail": str(exc)})

async def background_analysis_task():
    while True:
        try:
            logger.info("Running background analysis task")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error("Background task error: %s", e)
            await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    logger.info("PrepWise API starting up...")
    await speech_service.initialize()
    await video_service.initialize()
    await question_service.initialize()
    asyncio.create_task(background_analysis_task())
    logger.info("PrepWise API startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("PrepWise API shutting down...")
    await speech_service.cleanup()
    await video_service.cleanup()
    logger.info("PrepWise API shutdown complete")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
