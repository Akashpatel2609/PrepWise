from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    interview_sessions = relationship("InterviewSession", back_populates="user")

class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    
    id = Column(String(36), primary_key=True, index=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(100), nullable=False)
    job_description = Column(Text, nullable=False)
    minutes_per_question = Column(Integer, default=5)
    total_time = Column(Integer, default=30)
    num_questions = Column(Integer, nullable=False)
    status = Column(String(20), default="created")  # created, in_progress, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="interview_sessions")
    questions = relationship("Question", back_populates="session")
    responses = relationship("QuestionResponse", back_populates="session")

class Question(Base):
    __tablename__ = "questions"
    
    id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("interview_sessions.id"))
    question_text = Column(Text, nullable=False)
    question_type = Column(String(20))  # behavioral, technical, situational
    difficulty = Column(String(10), default="medium")
    expected_duration = Column(Integer, default=120)  # seconds
    order_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("InterviewSession", back_populates="questions")
    response = relationship("QuestionResponse", back_populates="question", uselist=False)

class QuestionResponse(Base):
    __tablename__ = "question_responses"
    
    id = Column(String(36), primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("interview_sessions.id"))
    question_id = Column(String(36), ForeignKey("questions.id"))
    audio_file_path = Column(String(255), nullable=True)
    video_file_path = Column(String(255), nullable=True)
    transcript = Column(Text, nullable=True)
    response_duration = Column(Integer, nullable=True)  # seconds
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("InterviewSession", back_populates="responses")
    question = relationship("Question", back_populates="response")
    speech_analysis = relationship("SpeechAnalysis", back_populates="response", uselist=False)
    video_analysis = relationship("VideoAnalysis", back_populates="response", uselist=False)

class SpeechAnalysis(Base):
    __tablename__ = "speech_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(String(36), ForeignKey("question_responses.id"))
    transcript = Column(Text)
    filler_words_count = Column(Integer, default=0)
    filler_words_details = Column(Text)  # JSON
    speaking_pace = Column(String(20))  # slow, normal, fast
    clarity_score = Column(Float)
    pronunciation_score = Column(Float)
    confidence_score = Column(Float)
    volume_level = Column(String(20))
    word_count = Column(Integer)
    words_per_minute = Column(Float)
    pause_analysis = Column(Text)  # JSON
    analysis_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    response = relationship("QuestionResponse", back_populates="speech_analysis")

class VideoAnalysis(Base):
    __tablename__ = "video_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    response_id = Column(String(36), ForeignKey("question_responses.id"))
    posture_score = Column(Float)
    posture_classification = Column(String(50))
    eye_contact_score = Column(Float)
    facial_expression = Column(String(50))
    gesture_analysis = Column(Text)  # JSON
    movement_analysis = Column(Text)  # JSON
    confidence_level = Column(String(20))
    engagement_score = Column(Float)
    professionalism_score = Column(Float)
    fidgeting_detected = Column(Boolean, default=False)
    fidgeting_frequency = Column(Float)
    frame_quality = Column(Text)  # JSON
    analysis_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    response = relationship("QuestionResponse", back_populates="video_analysis")

class FeedbackReport(Base):
    __tablename__ = "feedback_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), ForeignKey("interview_sessions.id"))
    overall_score = Column(Integer)
    speech_score = Column(Float)
    video_score = Column(Float)
    detailed_feedback = Column(Text)  # JSON
    recommendations = Column(Text)  # JSON
    strengths = Column(Text)  # JSON
    improvement_areas = Column(Text)  # JSON
    generated_at = Column(DateTime, default=datetime.utcnow)

class AnalysisLog(Base):
    __tablename__ = "analysis_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36))
    analysis_type = Column(String(20))  # speech, video, combined
    data_size = Column(Integer)  # bytes
    processing_time = Column(Float)  # seconds
    confidence_score = Column(Float)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
