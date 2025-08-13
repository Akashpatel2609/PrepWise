@echo off
echo 🚀 Starting PrepWise - AI-Powered Mock Interview Platform
echo ==================================================

REM Check if Docker is available
docker --version >nul 2>&1
if %errorlevel% == 0 (
    echo 🐳 Docker detected - Starting with Docker Compose...
    
    REM Build and start containers
    docker-compose up --build -d
    
    echo ✅ Services started successfully!
    echo.
    echo 🌐 Access the application:
    echo    Frontend: http://localhost:5000
    echo    Backend API: http://localhost:8000
    echo    API Docs: http://localhost:8000/docs
    echo.
    echo 📊 Monitor logs:
    echo    docker-compose logs -f
    echo.
    echo 🛑 Stop services:
    echo    docker-compose down
) else (
    echo ⚠️  Docker not found - Please install Docker and Docker Compose
    echo.
    echo Manual setup instructions:
    echo 1. Backend: cd backend ^&^& pip install -r requirements.txt ^&^& python main.py
    echo 2. Frontend: cd frontend ^&^& pip install -r requirements.txt ^&^& python app.py
)

pause