# PrepWise Project Structure

## Complete File Structure

```
PrepWise/
├── README.md                          # Main documentation
├── PROJECT_STRUCTURE.md              # This file
├── .env.template                      # Environment variables template
├── .dockerignore                      # Docker ignore file
├── docker-compose.yml                # Docker Compose configuration
├── Dockerfile.backend                # Backend Docker configuration
├── Dockerfile.frontend               # Frontend Docker configuration
├── start.sh                          # Linux/Mac startup script
├── start.bat                         # Windows startup script
├── keys.txt                          # API keys and configuration
├── INTEGRATION_SUCCESS.md            # Integration documentation
│
├── backend/                          # FastAPI Backend
│   ├── main.py                       # Main FastAPI application
│   ├── requirements.txt              # Python dependencies
│   │
│   ├── app/                          # Application modules
│   │   ├── __init__.py
│   │   ├── models/
│   │   │   └── database.py           # Database models
│   │   ├── routers/                  # API route handlers
│   │   │   ├── __init__.py
│   │   │   ├── analysis.py           # Analysis endpoints
│   │   │   ├── interview.py          # Interview management
│   │   │   └── questions.py          # Question generation
│   │   └── services/                 # Business logic services
│   │       ├── __init__.py
│   │       ├── speech_service.py     # Speech analysis with Whisper
│   │       ├── video_service.py      # Video analysis service
│   │       └── question_service.py   # Question generation service
│   │
│   ├── models/                       # AI Models and utilities
│   │   └── video/                    # Video analysis models
│   │       ├── final_best_model.h5   # Trained LSTM model (11.4MB)
│   │       ├── config.py             # Model configuration
│   │       └── detection_utils.py    # MediaPipe utilities
│   │
│   └── video_analysis/               # Video analysis integration
│       ├── __init__.py
│       └── service.py                # Video analysis service
│
├── frontend/                         # Flask Frontend
│   ├── app.py                        # Main Flask application
│   ├── requirements.txt              # Python dependencies
│   ├── analytics_data.json           # Analytics data storage
│   ├── start_server.bat             # Windows server start script
│   │
│   ├── templates/                    # HTML templates
│   │   ├── setup.html                # Interview setup page
│   │   ├── waiting_room.html         # Pre-interview waiting room
│   │   ├── interview.html            # Main interview interface
│   │   ├── feedback.html             # Post-interview feedback
│   │   └── analytics.html            # Performance analytics
│   │
│   └── static/                       # Static assets
│       ├── css/                      # Stylesheets
│       │   ├── main.css
│       │   └── style.css
│       └── js/                       # JavaScript files
│           └── interview.js          # Interview interface logic
```

## Key Components

### Backend Services

1. **Speech Analysis Service** (`speech_service.py`)
   - OpenAI Whisper integration for transcription
   - Filler word detection and analysis
   - Real-time audio processing
   - Performance scoring algorithms

2. **Video Analysis Service** (`video_service.py`)
   - Custom LSTM model for posture detection
   - MediaPipe integration for keypoint extraction
   - Real-time video frame processing
   - 4-class classification (Good Posture, Slouching, Confident Expression, Nervous Expression)

3. **Question Generation Service** (`question_service.py`)
   - AI-powered question generation
   - Template-based fallback questions
   - Job description analysis
   - Question categorization (behavioral, technical, situational)

### AI Models

1. **Video Analysis Model** (`final_best_model.h5`)
   - **Type**: Stacked LSTM neural network
   - **Input**: (30, 1662) - 30 frames with 1662 MediaPipe features
   - **Output**: 4 classes for posture/expression detection
   - **Size**: 11.4 MB
   - **Performance**: 17.4 FPS real-time processing

2. **Speech Analysis**
   - **Model**: OpenAI Whisper (base model)
   - **Features**: Transcription, filler detection, pace analysis
   - **Processing**: Real-time chunk-based analysis

3. **AI Feedback Generation**
   - **Model**: Google Gemini 1.5 Flash
   - **Purpose**: Comprehensive interview feedback and scoring
   - **Features**: Contextual analysis, improvement recommendations

### Frontend Pages

1. **Setup Page** (`setup.html`)
   - User information collection
   - Job description input
   - Interview configuration

2. **Waiting Room** (`waiting_room.html`)
   - Camera/microphone testing
   - Interview instructions
   - System checks

3. **Interview Interface** (`interview.html`)
   - Real-time video/audio capture
   - WebSocket communication with backend
   - Live feedback display
   - Question presentation

4. **Feedback Page** (`feedback.html`)
   - Comprehensive performance analysis
   - AI-generated recommendations
   - Detailed metrics and scoring
   - Progress visualization

5. **Analytics Dashboard** (`analytics.html`)
   - Historical performance tracking
   - Progress trends
   - Skill breakdown analysis
   - Multi-session comparisons

### Docker Configuration

1. **Backend Container**
   - Python 3.10 slim base image
   - TensorFlow, MediaPipe, Whisper dependencies
   - Model files and processing utilities
   - FastAPI server on port 8000

2. **Frontend Container**
   - Python 3.10 slim base image
   - Flask web server
   - Static assets and templates
   - Web interface on port 5000

3. **Docker Compose**
   - Service orchestration
   - Network configuration
   - Volume management
   - Health checks

## Data Flow

```
User Input → Frontend (Flask) → WebSocket → Backend (FastAPI) → AI Models → Analysis Results → Frontend Display
```

### Real-time Processing Pipeline

1. **Audio Stream**: Microphone → WebSocket → Whisper → Speech Analysis → Feedback
2. **Video Stream**: Camera → WebSocket → MediaPipe → LSTM Model → Posture Analysis → Feedback
3. **Question Flow**: Job Description → AI Generation → Question Display → User Response → Analysis

## Environment Variables

- `GEMINI_API_KEY`: Google Gemini API key for AI feedback
- `BACKEND_API_URL`: Backend service URL for frontend communication
- `VIDEO_MODEL_PATH`: Path to the video analysis model file
- `DEBUG`: Enable/disable debug mode
- `LOG_LEVEL`: Logging verbosity level

## Deployment Options

1. **Docker Compose** (Recommended)
   ```bash
   docker-compose up --build
   ```

2. **Manual Setup**
   ```bash
   # Backend
   cd backend && pip install -r requirements.txt && python main.py
   
   # Frontend  
   cd frontend && pip install -r requirements.txt && python app.py
   ```

3. **Production Deployment**
   - Use production WSGI server (Gunicorn) for Flask
   - Use production ASGI server (Uvicorn) for FastAPI
   - Configure reverse proxy (Nginx)
   - Set up SSL certificates
   - Configure environment variables

## Performance Characteristics

- **Real-time Processing**: 17.4 FPS video analysis
- **Model Size**: 11.4 MB video model, ~74 MB Whisper model
- **Memory Usage**: ~500 MB total system memory
- **Latency**: <100ms for real-time feedback
- **Scalability**: Single-user sessions, horizontally scalable

## Security Considerations

- API key management through environment variables
- WebSocket connection security
- File upload validation
- Session management and cleanup
- CORS configuration for cross-origin requests