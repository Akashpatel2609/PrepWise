import asyncio
import json
import logging
import random
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class QuestionGeneratorService:
    """Service for generating interview questions using AI models"""
    
    def __init__(self):
        self.deepseek_api_key = None
        self.ollama_endpoint = None
        self.question_cache = {}
        
    async def initialize(self):
        """Initialize the question generation service"""
        try:
            # Initialize AI model connections
            # In production, set up actual API connections
            self.deepseek_api_key = "YOUR_DEEPSEEK_API_KEY_HERE"
            self.ollama_endpoint = "http://localhost:11434"  # Default Ollama endpoint
            
            logger.info("Question generator service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize question generator service: {str(e)}")
            
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Question generator service cleanup complete")
    
    async def generate_questions_ai(self, job_description: str, num_questions: int, 
                                  difficulty: str = "medium") -> List[Dict]:
        """Generate questions using AI (Deepseek or Ollama)"""
        try:
            # Create cache key
            cache_key = f"{hash(job_description)}_{num_questions}_{difficulty}"
            
            # Check cache first
            if cache_key in self.question_cache:
                logger.info("Returning cached questions")
                return self.question_cache[cache_key]
            
            # Prepare AI prompt
            prompt = self._create_question_prompt(job_description, num_questions, difficulty)
            
            # Try Deepseek first, then fallback to Ollama
            questions = await self._try_deepseek_generation(prompt, num_questions)
            
            if not questions:
                questions = await self._try_ollama_generation(prompt, num_questions)
            
            if not questions:
                # Fallback to template-based generation
                questions = self._generate_fallback_questions(job_description, num_questions, difficulty)
            
            # Cache the results
            self.question_cache[cache_key] = questions
            
            return questions
            
        except Exception as e:
            logger.error(f"AI question generation error: {str(e)}")
            return self._generate_fallback_questions(job_description, num_questions, difficulty)
    
    def _create_question_prompt(self, job_description: str, num_questions: int, difficulty: str) -> str:
        """Create AI prompt for question generation"""
        
        difficulty_instructions = {
            "easy": "Generate straightforward questions suitable for entry-level positions.",
            "medium": "Generate moderate difficulty questions for mid-level positions.",
            "hard": "Generate challenging questions for senior-level positions."
        }
        
        prompt = f"""
        You are an expert interview coach. Generate {num_questions} professional interview questions 
        based on the following job description. {difficulty_instructions.get(difficulty, "")}
        
        Job Description:
        {job_description}
        
        Requirements:
        - Questions should be relevant to the role and industry
        - Include a mix of behavioral, technical, and situational questions
        - Each question should be clear and professional
        - Avoid overly generic questions
        - Questions should help assess the candidate's fit for this specific role
        
        Please provide exactly {num_questions} questions in a numbered list format.
        """
        
        return prompt
    
    async def _try_deepseek_generation(self, prompt: str, num_questions: int) -> Optional[List[Dict]]:
        """Try generating questions using Deepseek API"""
        try:
            # Placeholder for Deepseek API call
            # In production, implement actual API call:
            
            # import httpx
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(
            #         "https://api.deepseek.com/v1/chat/completions",
            #         headers={"Authorization": f"Bearer {self.deepseek_api_key}"},
            #         json={
            #             "model": "deepseek-chat",
            #             "messages": [{"role": "user", "content": prompt}],
            #             "max_tokens": 1000,
            #             "temperature": 0.7
            #         }
            #     )
            #     
            #     if response.status_code == 200:
            #         result = response.json()
            #         content = result["choices"][0]["message"]["content"]
            #         return self._parse_ai_response(content, num_questions)
            
            logger.info("Deepseek API not configured - using fallback")
            return None
            
        except Exception as e:
            logger.error(f"Deepseek generation error: {str(e)}")
            return None
    
    async def _try_ollama_generation(self, prompt: str, num_questions: int) -> Optional[List[Dict]]:
        """Try generating questions using local Ollama"""
        try:
            # Placeholder for Ollama API call
            # In production, implement actual API call:
            
            # import httpx
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(
            #         f"{self.ollama_endpoint}/api/generate",
            #         json={
            #             "model": "llama2",  # or another model
            #             "prompt": prompt,
            #             "stream": False
            #         }
            #     )
            #     
            #     if response.status_code == 200:
            #         result = response.json()
            #         content = result["response"]
            #         return self._parse_ai_response(content, num_questions)
            
            logger.info("Ollama not available - using fallback")
            return None
            
        except Exception as e:
            logger.error(f"Ollama generation error: {str(e)}")
            return None
    
    def _parse_ai_response(self, ai_response: str, expected_count: int) -> List[Dict]:
        """Parse AI response into structured question format"""
        questions = []
        lines = ai_response.strip().split('\n')
        
        current_question = ""
        question_counter = 0
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Check if line starts with a number (indicating a new question)
            if line[0].isdigit() and ('.' in line or ')' in line):
                if current_question:
                    questions.append(self._format_question(current_question, question_counter))
                    question_counter += 1
                
                # Extract question text (remove numbering)
                current_question = line.split('.', 1)[-1].split(')', 1)[-1].strip()
            else:
                # Continue current question
                current_question += " " + line
        
        # Add the last question
        if current_question:
            questions.append(self._format_question(current_question, question_counter))
        
        # Ensure we have the expected number of questions
        while len(questions) < expected_count:
            questions.append(self._format_question(
                "Tell me about a project you're particularly proud of.", 
                len(questions)
            ))
        
        return questions[:expected_count]
    
    def _format_question(self, question_text: str, index: int) -> Dict:
        """Format question into standard structure"""
        # Determine question type based on content
        question_type = "behavioral"
        if any(word in question_text.lower() for word in ["technical", "technology", "code", "programming"]):
            question_type = "technical"
        elif any(word in question_text.lower() for word in ["would you", "how would", "what if"]):
            question_type = "situational"
        
        return {
            "question_id": f"ai_q_{index + 1}",
            "question_text": question_text.strip(),
            "question_type": question_type,
            "difficulty": "medium",
            "expected_duration": 120,  # 2 minutes default
            "source": "ai_generated"
        }
    
    def _generate_fallback_questions(self, job_description: str, num_questions: int, 
                                   difficulty: str) -> List[Dict]:
        """Generate fallback questions when AI is not available"""
        
        # Analyze job description for keywords
        keywords = self._extract_job_keywords(job_description.lower())
        
        # Question templates by category
        behavioral_questions = [
            "Tell me about yourself and your background.",
            "Describe a challenging situation you faced at work and how you handled it.",
            "Give me an example of a time when you had to work with a difficult team member.",
            "Tell me about a project you're particularly proud of.",
            "Describe a time when you made a mistake and how you handled it.",
            "How do you handle constructive criticism?",
            "Tell me about a time when you had to learn something new quickly.",
            "Describe your leadership style with a specific example.",
            "How do you prioritize your work when facing multiple deadlines?",
            "Tell me about a time when you had to persuade someone to see your point of view."
        ]
        
        technical_questions = [
            f"What experience do you have with {', '.join(keywords[:3])}?" if keywords else "What technical skills are you most proud of?",
            "How do you approach problem-solving in your field?",
            "Describe a technical challenge you recently overcame.",
            "How do you stay updated with the latest industry trends?",
            "What tools and technologies do you prefer to work with and why?",
            "How do you ensure quality in your work?",
            "Describe your approach to learning new technologies.",
            "What methodologies do you follow in your work process?",
            "How do you handle technical debt or legacy systems?",
            "Explain a complex concept from your field to someone non-technical."
        ]
        
        situational_questions = [
            "How would you handle a project with an unrealistic deadline?",
            "What would you do if you disagreed with your manager's approach?",
            "How would you approach a task outside your area of expertise?",
            "What would you do if you discovered an error in completed work?",
            "How would you handle an unhappy client or customer?",
            "What would you do if team members weren't contributing equally?",
            "How would you approach working with outdated technology?",
            "What would you do if you were falling behind on a project?",
            "How would you handle a situation requiring resources you don't have?",
            "What would you do if priorities changed suddenly during a project?"
        ]
        
        # Select questions based on difficulty and job description
        all_questions = []
        
        # Distribute question types
        behavioral_count = max(1, num_questions // 3)
        technical_count = max(1, num_questions // 3)
        situational_count = num_questions - behavioral_count - technical_count
        
        # Select behavioral questions
        selected_behavioral = random.sample(behavioral_questions, min(behavioral_count, len(behavioral_questions)))
        for i, q in enumerate(selected_behavioral):
            all_questions.append({
                "question_id": f"fallback_b_{i+1}",
                "question_text": q,
                "question_type": "behavioral",
                "difficulty": difficulty,
                "expected_duration": 120,
                "source": "template"
            })
        
        # Select technical questions
        selected_technical = random.sample(technical_questions, min(technical_count, len(technical_questions)))
        for i, q in enumerate(selected_technical):
            all_questions.append({
                "question_id": f"fallback_t_{i+1}",
                "question_text": q,
                "question_type": "technical",
                "difficulty": difficulty,
                "expected_duration": 150,
                "source": "template"
            })
        
        # Select situational questions
        selected_situational = random.sample(situational_questions, min(situational_count, len(situational_questions)))
        for i, q in enumerate(selected_situational):
            all_questions.append({
                "question_id": f"fallback_s_{i+1}",
                "question_text": q,
                "question_type": "situational",
                "difficulty": difficulty,
                "expected_duration": 135,
                "source": "template"
            })
        
        # Shuffle and return
        random.shuffle(all_questions)
        return all_questions[:num_questions]
    
    def _extract_job_keywords(self, job_description: str) -> List[str]:
        """Extract relevant keywords from job description"""
        # Common technical keywords
        tech_keywords = [
            "python", "javascript", "java", "react", "node", "sql", "mongodb",
            "aws", "docker", "kubernetes", "api", "frontend", "backend",
            "machine learning", "data science", "analytics", "cloud"
        ]
        
        found_keywords = []
        for keyword in tech_keywords:
            if keyword in job_description:
                found_keywords.append(keyword)
        
        return found_keywords[:5]  # Return top 5 keywords
    
    async def get_follow_up_questions(self, original_question: str, response: str) -> List[Dict]:
        """Generate follow-up questions based on response"""
        follow_ups = [
            "Can you elaborate on that point?",
            "What was the outcome of that situation?",
            "How did that experience change your approach?",
            "What would you do differently next time?",
            "Can you give me another example of this?"
        ]
        
        return [{
            "question_id": f"followup_{i+1}",
            "question_text": q,
            "question_type": "follow_up",
            "difficulty": "medium",
            "expected_duration": 60,
            "source": "follow_up"
        } for i, q in enumerate(follow_ups[:2])]
    
    async def customize_questions_for_role(self, base_questions: List[Dict], 
                                         role_type: str) -> List[Dict]:
        """Customize questions based on specific role type"""
        # Role-specific modifications
        role_modifiers = {
            "leadership": "How do you",
            "technical": "What is your experience with",
            "creative": "Describe your creative process for",
            "analytical": "How do you analyze"
        }
        
        # This is a placeholder for role customization logic
        return base_questions
