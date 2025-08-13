// Interview Management JavaScript
class InterviewManager {
    constructor() {
        this.sessionId = null;
        this.mediaStream = null;
        this.mediaRecorder = null;
        this.websocket = null;
        this.isRecording = false;
        this.analysisData = {
            speech: [],
            video: [],
            posture: []
        };
    }

    // Initialize WebSocket connection for real-time analysis
    initializeWebSocket(sessionId) {
        this.sessionId = sessionId;
        this.websocket = new WebSocket(`ws://localhost:8000/ws/interview/${sessionId}`);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected for real-time analysis');
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleAnalysisData(data);
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    // Handle incoming analysis data
    handleAnalysisData(data) {
        switch(data.type) {
            case 'speech_analysis':
                this.updateSpeechAnalysis(data.data);
                break;
            case 'video_analysis':
                this.updateVideoAnalysis(data.data);
                break;
            case 'posture_analysis':
                this.updatePostureAnalysis(data.data);
                break;
        }
    }

    // Update speech analysis display
    updateSpeechAnalysis(data) {
        const speechStatus = document.getElementById('speechStatus');
        if (speechStatus) {
            if (data.filler_words && data.filler_words.count > 0) {
                speechStatus.textContent = `Filler words detected: ${data.filler_words.count}`;
            } else {
                speechStatus.textContent = 'Clear speech';
            }
        }
        this.analysisData.speech.push(data);
    }

    // Update video analysis display
    updateVideoAnalysis(data) {
        const postureStatus = document.getElementById('postureStatus');
        if (postureStatus) {
            postureStatus.textContent = data.posture || 'Analyzing posture...';
        }
        this.analysisData.video.push(data);
    }

    // Update posture analysis display
    updatePostureAnalysis(data) {
        const postureStatus = document.getElementById('postureStatus');
        if (postureStatus) {
            postureStatus.textContent = data.status || 'Good posture';
        }
        this.analysisData.posture.push(data);
    }

    // Start media recording
    async startRecording() {
        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 }
                },
                audio: {
                    sampleRate: 44100,
                    channelCount: 2
                }
            });

            // Display video
            const videoElement = document.getElementById('interviewWebcam') || 
                                document.getElementById('webcam');
            if (videoElement) {
                videoElement.srcObject = this.mediaStream;
            }

            // Setup MediaRecorder
            this.mediaRecorder = new MediaRecorder(this.mediaStream, {
                mimeType: 'video/webm;codecs=vp9'
            });

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && this.websocket) {
                    // Send video data for analysis
                    this.sendDataForAnalysis(event.data, 'video');
                }
            };

            // Start recording in chunks
            this.mediaRecorder.start(1000); // 1 second chunks
            this.isRecording = true;

            // Start audio analysis
            this.startAudioAnalysis();

            return true;
        } catch (error) {
            console.error('Error starting recording:', error);
            return false;
        }
    }

    // Start audio analysis
    startAudioAnalysis() {
        if (!this.mediaStream) return;

        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(this.mediaStream);
        const analyser = audioContext.createAnalyser();
        
        analyser.fftSize = 256;
        source.connect(analyser);

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        const analyzeAudio = () => {
            if (this.isRecording) {
                analyser.getByteFrequencyData(dataArray);
                
                // Calculate audio level
                const average = dataArray.reduce((a, b) => a + b) / bufferLength;
                
                // Send audio level for analysis
                if (this.websocket && average > 10) { // Only send if there's significant audio
                    this.websocket.send(JSON.stringify({
                        type: 'audio_level',
                        data: { level: average, timestamp: Date.now() }
                    }));
                }

                requestAnimationFrame(analyzeAudio);
            }
        };

        analyzeAudio();
    }

    // Send data for analysis
    sendDataForAnalysis(data, type) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            const message = {
                type: type,
                sessionId: this.sessionId,
                timestamp: Date.now(),
                data: data
            };
            this.websocket.send(JSON.stringify(message));
        }
    }

    // Stop recording
    stopRecording() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
        }

        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
        }

        if (this.websocket) {
            this.websocket.close();
        }
    }

    // Toggle camera
    toggleCamera() {
        if (this.mediaStream) {
            const videoTrack = this.mediaStream.getVideoTracks()[0];
            if (videoTrack) {
                videoTrack.enabled = !videoTrack.enabled;
                return videoTrack.enabled;
            }
        }
        return false;
    }

    // Toggle microphone
    toggleMicrophone() {
        if (this.mediaStream) {
            const audioTrack = this.mediaStream.getAudioTracks()[0];
            if (audioTrack) {
                audioTrack.enabled = !audioTrack.enabled;
                return audioTrack.enabled;
            }
        }
        return false;
    }

    // Get analysis summary
    getAnalysisSummary() {
        return {
            speech: this.analysisData.speech,
            video: this.analysisData.video,
            posture: this.analysisData.posture,
            sessionId: this.sessionId
        };
    }
}

// Question Generator
class QuestionGenerator {
    constructor() {
        this.apiEndpoint = '/api/generate-question';
        this.questions = [];
        this.currentIndex = 0;
    }

    async generateQuestions(jobDescription, count) {
        try {
            const response = await fetch('/api/generate-questions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    job_description: jobDescription,
                    count: count
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.questions = data.questions;
                return this.questions;
            }
        } catch (error) {
            console.error('Error generating questions:', error);
        }

        // Fallback questions
        return this.getFallbackQuestions(count);
    }

    getFallbackQuestions(count) {
        const fallbackQuestions = [
            "Tell me about yourself and your background.",
            "What interests you about this role and our company?",
            "Describe a challenging project you've worked on recently.",
            "How do you handle working under pressure and tight deadlines?",
            "What are your greatest strengths and how do they apply to this role?",
            "Describe a time when you had to work with a difficult team member.",
            "Where do you see yourself in 5 years?",
            "Why are you looking to leave your current position?",
            "What is your approach to learning new technologies or skills?",
            "Do you have any questions for us about the role or company?"
        ];

        return fallbackQuestions.slice(0, count);
    }

    getNextQuestion() {
        if (this.currentIndex < this.questions.length) {
            return this.questions[this.currentIndex++];
        }
        return null;
    }

    getCurrentQuestionIndex() {
        return this.currentIndex;
    }

    getTotalQuestions() {
        return this.questions.length;
    }
}

// Timer Management
class TimerManager {
    constructor(minutes, onTimeUp) {
        this.totalSeconds = minutes * 60;
        this.remainingSeconds = this.totalSeconds;
        this.interval = null;
        this.onTimeUp = onTimeUp;
        this.isPaused = false;
    }

    start() {
        this.interval = setInterval(() => {
            if (!this.isPaused) {
                this.remainingSeconds--;
                this.updateDisplay();

                if (this.remainingSeconds <= 0) {
                    this.stop();
                    if (this.onTimeUp) {
                        this.onTimeUp();
                    }
                }
            }
        }, 1000);
    }

    pause() {
        this.isPaused = true;
    }

    resume() {
        this.isPaused = false;
    }

    stop() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    reset(minutes) {
        this.stop();
        this.totalSeconds = minutes * 60;
        this.remainingSeconds = this.totalSeconds;
        this.updateDisplay();
    }

    updateDisplay() {
        const minutes = Math.floor(this.remainingSeconds / 60);
        const seconds = this.remainingSeconds % 60;
        const display = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        
        const timerElement = document.getElementById('questionTimer');
        if (timerElement) {
            timerElement.textContent = display;
            
            // Add warning colors
            if (this.remainingSeconds <= 30) {
                timerElement.style.color = '#dc3545';
            } else if (this.remainingSeconds <= 60) {
                timerElement.style.color = '#ffc107';
            } else {
                timerElement.style.color = '#058ED9';
            }
        }
    }

    getTimeRemaining() {
        return this.remainingSeconds;
    }
}

// Global instances
window.interviewManager = new InterviewManager();
window.questionGenerator = new QuestionGenerator();
window.timerManager = null;

// Utility functions
window.PrepWiseUtils = {
    // Format time duration
    formatTime: (seconds) => {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    },

    // Calculate WPM (Words Per Minute)
    calculateWPM: (text, durationSeconds) => {
        const words = text.split(' ').length;
        const minutes = durationSeconds / 60;
        return Math.round(words / minutes);
    },

    // Detect device capabilities
    detectDeviceCapabilities: async () => {
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            const capabilities = {
                camera: devices.some(device => device.kind === 'videoinput'),
                microphone: devices.some(device => device.kind === 'audioinput'),
                speaker: devices.some(device => device.kind === 'audiooutput')
            };
            return capabilities;
        } catch (error) {
            console.error('Error detecting device capabilities:', error);
            return { camera: false, microphone: false, speaker: false };
        }
    },

    // Save interview data to local storage
    saveInterviewData: (sessionId, data) => {
        const storageKey = `interview_${sessionId}`;
        localStorage.setItem(storageKey, JSON.stringify(data));
    },

    // Load interview data from local storage
    loadInterviewData: (sessionId) => {
        const storageKey = `interview_${sessionId}`;
        const data = localStorage.getItem(storageKey);
        return data ? JSON.parse(data) : null;
    },

    // Generate unique session ID
    generateSessionId: () => {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        InterviewManager,
        QuestionGenerator,
        TimerManager,
        PrepWiseUtils
    };
}
