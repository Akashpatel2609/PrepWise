# PrepWise - AI-Powered Mock Interview Platform

PrepWise is an intelligent mock interview platform that provides real-time feedback on speech patterns, body language, and overall interview performance using advanced AI models.

## Features

- **Real-time Speech Analysis**: Uses OpenAI Whisper for transcription and analysis
- **Body Language Detection**: Custom LSTM model for posture and expression analysis
- **AI-Powered Feedback**: Comprehensive performance evaluation using Google Gemini
- **Interactive Interview Experience**: Simulated interview environment with dynamic questions
- **Performance Analytics**: Detailed metrics and progress tracking
- **Docker Support**: Easy deployment with Docker containers

## Technology Stack

- **Frontend**: Flask, HTML5, CSS3, JavaScript
- **Backend**: FastAPI, WebSocket for real-time communication
- **AI Models**: 
  - OpenAI Whisper (speech analysis)
  - Custom LSTM model (video/posture analysis)
  - Google Gemini (feedback generation)
- **Computer Vision**: MediaPipe for pose/gesture detection
- **Database**: SQLAlchemy with SQLite
- **Deployment**: Docker & Docker Compose

## Quick Start with Docker

### Prerequisites
- Docker and Docker Compose installed
- Webcam and microphone access

### Run with Docker Compose

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd PrepWise
   ```

2. Build and run the containers:
   ```bash
   docker-compose up --build
   ```

3. Access the application:
   - Frontend: http://localhost:5000
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Environment Configuration

Create a `.env` file in the root directory:
```env
# Google Gemini API Key (for AI feedback)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Custom model paths
VIDEO_MODEL_PATH=/app/models/video/final_best_model.h5
```

## Manual Setup (Development)

### Prerequisites
- Python 3.10+
- pip package manager
- Webcam and microphone access

### Backend Setup

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the backend server:
   ```bash
   python main.py
   ```

### Frontend Setup

1. Navigate to frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure API key in `app.py`:
   ```python
   GEMINI_API_KEY = "your_gemini_api_key_here"
   ```

4. Run the frontend server:
   ```bash
   python app.py
   ```

## Model Files

The application includes a pre-trained video analysis model:
- **Location**: `backend/models/video/final_best_model.h5`
- **Type**: LSTM neural network for posture/expression detection
- **Size**: ~11.4 MB
- **Classes**: Good Posture, Slouching, Confident Expression, Nervous Expression

## Usage

1. **Setup**: Enter your name, job description, and interview preferences
2. **Waiting Room**: Review instructions and test your camera/microphone
3. **Interview**: Answer questions while receiving real-time feedback
4. **Feedback**: Review detailed AI-powered performance analysis and recommendations
5. **Analytics**: Track progress over multiple interview sessions

## API Endpoints

### Core Endpoints
- `GET /api/health` - Health check
- `POST /api/interview/create` - Create interview session
- `WebSocket /ws/interview/{session_id}` - Real-time analysis

### Analysis Endpoints
- `POST /api/analysis/speech-analysis` - Speech analysis with Whisper
- `POST /api/analysis/video` - Video/posture analysis
- `GET /api/analysis/report/{session_id}` - Generate feedback report

### Question Generation
- `POST /api/questions/generate` - Generate interview questions
- `GET /api/questions/sample/{type}` - Get sample questions by type

## Architecture

```
┌─────────────────┐    WebSocket    ┌─────────────────┐
│   Frontend      │◄──────────────►│   Backend       │
│   (Flask)       │                 │   (FastAPI)     │
│   Port: 5000    │                 │   Port: 8000    │
└─────────────────┘                 └─────────────────┘
                                            │
                                            ▼
                                    ┌─────────────────┐
                                    │   AI Models     │
                                    │   - Whisper     │
                                    │   - LSTM        │
                                    │   - MediaPipe   │
                                    │   - Gemini      │
                                    └─────────────────┘
```

## Performance Metrics

### Video Model Performance
- **Real-time Processing**: 17.4 FPS
- **Model Size**: 11.4 MB
- **Inference Time**: ~503ms per sequence
- **Accuracy**: Optimized for 4-class posture detection

### Speech Analysis
- **Transcription**: OpenAI Whisper (base model)
- **Real-time**: Chunk-based processing
- **Features**: Filler word detection, pace analysis, clarity scoring

## Docker Configuration

### Services
- **Backend**: FastAPI application with AI models
- **Frontend**: Flask web application
- **Network**: Internal Docker network for service communication
- **Volumes**: Persistent storage for models and logs

### Build Commands
```bash
# Build individual services
docker build -f Dockerfile.backend -t prepwise-backend .
docker build -f Dockerfile.frontend -t prepwise-frontend .

# Run with compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Troubleshooting

### Common Issues

1. **Model Loading Error**:
   - Ensure video model file exists at `backend/models/video/final_best_model.h5`
   - Check TensorFlow installation

2. **Whisper Installation**:
   ```bash
   pip install openai-whisper
   ```

3. **MediaPipe Issues**:
   ```bash
   pip install mediapipe opencv-python
   ```

4. **Docker Build Fails**:
   - Ensure Docker has sufficient memory (4GB+)
   - Check system dependencies in Dockerfile

### Performance Optimization

1. **GPU Support**: Add NVIDIA runtime for GPU acceleration
2. **Model Optimization**: Use TensorFlow Lite for faster inference
3. **Caching**: Enable model caching for repeated use

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Submit a pull request with detailed description

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Docker logs: `docker-compose logs`
3. Open an issue on GitHub with detailed error information