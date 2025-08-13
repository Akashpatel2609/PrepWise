from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import json
import random
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class QuestionGenerationRequest(BaseModel):
    job_description: str
    num_questions: int
    difficulty_level: Optional[str] = "medium"  # easy, medium, hard
    question_types: Optional[List[str]] = ["behavioral", "technical", "situational"]

class QuestionResponse(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    difficulty: str
    expected_duration: int  # in seconds

class QuestionSet(BaseModel):
    session_id: str
    questions: List[QuestionResponse]
    total_questions: int
    estimated_duration: int

# Mock question database (replace with AI generation)
QUESTION_TEMPLATES = {
    "behavioral": [
        "Tell me about yourself and your background.",
        "Describe a time when you faced a significant challenge at work. How did you handle it?",
        "Give me an example of a time when you had to work with a difficult team member.",
        "Tell me about a project you're particularly proud of.",
        "Describe a situation where you had to learn something new quickly.",
        "How do you handle constructive criticism?",
        "Tell me about a time when you made a mistake. How did you handle it?",
        "Describe your leadership style with an example.",
        "How do you prioritize your work when you have multiple deadlines?",
        "Tell me about a time when you had to persuade someone to see your point of view."
    ],
    "technical": [
        "What programming languages are you most comfortable with and why?",
        "How do you approach debugging a complex problem?",
        "Explain a technical concept you recently learned.",
        "How do you stay updated with the latest technology trends?",
        "Describe your experience with databases and data modeling.",
        "What is your approach to code review and testing?",
        "How do you handle technical debt in a project?",
        "Explain your understanding of software architecture principles.",
        "Describe a technical challenge you solved recently.",
        "How do you ensure code quality and maintainability?"
    ],
    "situational": [
        "How would you handle a situation where you disagree with your manager's decision?",
        "What would you do if you were assigned a task outside your expertise?",
        "How would you approach a project with an unrealistic deadline?",
        "What would you do if you discovered a significant error in a project after it was completed?",
        "How would you handle a situation where a client is unhappy with your work?",
        "What would you do if you had to work with outdated technology?",
        "How would you approach training a new team member?",
        "What would you do if you were falling behind on a project deadline?",
        "How would you handle a situation where you need resources that aren't available?",
        "What would you do if you found out a colleague was not pulling their weight?"
    ]
}

@router.post("/generate", response_model=QuestionSet)
async def generate_questions(request: QuestionGenerationRequest):
    """Generate interview questions based on job description"""
    try:
        questions = []
        question_types = request.question_types or ["behavioral", "technical", "situational"]
        
        # For now, use random selection from templates
        # In production, this would use AI (Deepseek/Ollama) to generate based on job description
        
        for i in range(request.num_questions):
            question_type = random.choice(question_types)
            question_text = random.choice(QUESTION_TEMPLATES[question_type])
            
            # Estimate duration based on question type and difficulty
            base_duration = 120  # 2 minutes
            if request.difficulty_level == "easy":
                duration = base_duration - 30
            elif request.difficulty_level == "hard":
                duration = base_duration + 60
            else:
                duration = base_duration
                
            question = QuestionResponse(
                question_id=f"q_{i+1}",
                question_text=question_text,
                question_type=question_type,
                difficulty=request.difficulty_level,
                expected_duration=duration
            )
            questions.append(question)
        
        total_duration = sum([q.expected_duration for q in questions])
        
        question_set = QuestionSet(
            session_id=f"session_{random.randint(1000, 9999)}",
            questions=questions,
            total_questions=len(questions),
            estimated_duration=total_duration
        )
        
        return question_set
    
    except Exception as e:
        logger.error(f"Question generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate questions: {str(e)}")

@router.get("/sample/{question_type}")
async def get_sample_questions(question_type: str, count: int = 5):
    """Get sample questions by type"""
    if question_type not in QUESTION_TEMPLATES:
        raise HTTPException(status_code=400, detail="Invalid question type")
    
    sample_questions = random.sample(
        QUESTION_TEMPLATES[question_type], 
        min(count, len(QUESTION_TEMPLATES[question_type]))
    )
    
    return {
        "question_type": question_type,
        "questions": sample_questions,
        "count": len(sample_questions)
    }

@router.get("/types")
async def get_question_types():
    """Get available question types"""
    return {
        "types": list(QUESTION_TEMPLATES.keys()),
        "descriptions": {
            "behavioral": "Questions about past experiences and behavior",
            "technical": "Questions about technical skills and knowledge",
            "situational": "Hypothetical scenarios and problem-solving questions"
        }
    }

@router.post("/ai-generate")
async def ai_generate_questions(request: QuestionGenerationRequest):
    """Generate questions using AI (placeholder for Deepseek/Ollama integration)"""
    try:
        # Placeholder for AI integration
        # This is where you would integrate with Deepseek or Ollama API
        
        ai_prompt = f"""
        Generate {request.num_questions} interview questions for the following job description:
        
        Job Description: {request.job_description}
        
        Question Types: {', '.join(request.question_types)}
        Difficulty Level: {request.difficulty_level}
        
        Return questions that are relevant, professional, and appropriate for the role.
        """
        
        # Mock AI response (replace with actual AI call)
        ai_questions = [
            f"Based on the job description, {random.choice(QUESTION_TEMPLATES['behavioral'])}"
            for _ in range(request.num_questions)
        ]
        
        questions = []
        for i, question_text in enumerate(ai_questions):
            question = QuestionResponse(
                question_id=f"ai_q_{i+1}",
                question_text=question_text,
                question_type=random.choice(request.question_types),
                difficulty=request.difficulty_level,
                expected_duration=120
            )
            questions.append(question)
        
        question_set = QuestionSet(
            session_id=f"ai_session_{random.randint(1000, 9999)}",
            questions=questions,
            total_questions=len(questions),
            estimated_duration=sum([q.expected_duration for q in questions])
        )
        
        return question_set
    
    except Exception as e:
        logger.error(f"AI question generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI question generation failed: {str(e)}")

@router.get("/")
async def get_random_question():
    """Get a single random question"""
    question_type = random.choice(list(QUESTION_TEMPLATES.keys()))
    question_text = random.choice(QUESTION_TEMPLATES[question_type])
    
    return {
        "question": question_text,
        "type": question_type,
        "id": f"random_{random.randint(100, 999)}"
    }
