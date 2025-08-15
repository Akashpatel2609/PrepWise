from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import uuid
import requests
import json
import os
import re
from datetime import datetime
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = ''

# Google Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCV9sK0q3QZ9q9kaGnF2FdsCxI0h1LZfek")
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# Enable AI analysis with Gemini
USE_AI_ANALYSIS = True  # Enable AI API calls with Gemini

# Backend API base URL (FastAPI will run on port 8000)
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

# Temporary storage for large data that can't fit in session cookies
temp_data_store = {}

# Analytics data storage file
ANALYTICS_DATA_FILE = 'analytics_data.json'

def load_analytics_data():
    """Load analytics data from JSON file"""
    if os.path.exists(ANALYTICS_DATA_FILE):
        try:
            with open(ANALYTICS_DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_analytics_data(data):
    """Save analytics data to JSON file"""
    try:
        with open(ANALYTICS_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving analytics data: {e}")

def store_session_analytics(session_data, scores):
    """Store session data for analytics tracking"""
    analytics_data = load_analytics_data()
    
    user_name = session_data.get('name', 'Anonymous')
    session_id = session_data.get('session_id', str(uuid.uuid4()))
    
    # Create user data structure if it doesn't exist
    if user_name not in analytics_data:
        analytics_data[user_name] = {
            'sessions': [],
            'total_sessions': 0,
            'average_score': 0
        }
    
    # Store session data
    session_record = {
        'session_id': session_id,
        'timestamp': datetime.now().isoformat(),
        'overall_score': scores.get('overall_score', 0),
        'speech_score': scores.get('speech_score', 0),
        'posture_score': scores.get('posture_score', 0),
        'confidence_score': scores.get('confidence_score', 0),
        'response_time_score': scores.get('response_time_score', 0),
        'content_score': scores.get('content_score', 0),
        'total_words': session_data.get('total_words', 0),
        'questions_answered': session_data.get('questions_answered', 0),
        'total_questions': session_data.get('total_questions', 1),
        'filler_words_count': sum(session_data.get('filler_words', {}).values()),
        'job_description': session_data.get('job_description', '')[:100] + '...'  # Truncated for storage
    }
    
    analytics_data[user_name]['sessions'].append(session_record)
    analytics_data[user_name]['total_sessions'] = len(analytics_data[user_name]['sessions'])
    
    # Calculate average score
    if analytics_data[user_name]['sessions']:
        total_score = sum([s['overall_score'] for s in analytics_data[user_name]['sessions']])
        analytics_data[user_name]['average_score'] = total_score / len(analytics_data[user_name]['sessions'])
    
    save_analytics_data(analytics_data)
    return analytics_data

@app.route('/')
@app.route('/setup')
def setup():
    """Interview Setup Page - Page 1"""
    return render_template('setup.html')

@app.route('/camera-test')
def camera_test():
    """Camera and microphone test page for debugging"""
    return render_template('camera_test.html')

@app.route('/waiting-room', methods=['GET', 'POST'])
def waiting_room():
    """Waiting Room Page - Page 2"""
    if request.method == 'POST':
        print(f"📝 POST to waiting room. Form data: {request.form}")
        # Store interview details in session (truncate job description to prevent cookie size issues)
        session['name'] = request.form.get('name')
        
        # Truncate job description to prevent session cookie from exceeding browser limits
        job_desc = request.form.get('job_description', '')
        if len(job_desc) > 500:  # Limit to 500 characters
            job_desc = job_desc[:500] + "... [truncated for session storage]"
        session['job_description'] = job_desc
        
        session['minutes_per_question'] = int(request.form.get('minutes_per_question', 5))
        session['total_time'] = int(request.form.get('total_time', 30))
        
        # Calculate number of questions
        num_questions = session['total_time'] // session['minutes_per_question']
        session['num_questions'] = num_questions
        session['session_id'] = str(uuid.uuid4())
        
        # Store full job description separately for later use (not in session)
        full_job_desc = request.form.get('job_description', '')
        session_id = str(uuid.uuid4())
        
        # Store full job description in temporary storage
        temp_data_store[session_id] = {
            'full_job_description': full_job_desc,
            'timestamp': datetime.now()
        }
        
        session['session_id'] = session_id
        
        print(f"✅ Session created successfully!")
        print(f"   Session ID: {session_id}")
        print(f"   Number of questions: {num_questions}")
        print(f"   Job description length: {len(full_job_desc)} chars (stored: {len(job_desc)} chars)")
        
        # Estimate session size
        session_size = len(str(dict(session)).encode('utf-8'))
        print(f"   Estimated session size: {session_size} bytes (limit: 4093)")
    else:
        print(f"🔍 GET to waiting room. Current session: {dict(session)}")
        # GET request - check if we have session data, if not redirect to setup
        if 'session_id' not in session:
            print("❌ No session found in GET request, redirecting to setup")
            return redirect(url_for('setup'))
        
    return render_template('waiting_room.html')

@app.route('/interview')
def interview():
    """Interview Interface Page - Page 3"""
    print(f"🔍 Interview route accessed.")
    print(f"   Session contents: {dict(session)}")
    print(f"   Session ID exists: {'session_id' in session}")
    print(f"   Session keys: {list(session.keys())}")
    
    # Use actual session data or redirect to setup if missing
    if 'session_id' not in session:
        print("❌ No session_id found, redirecting to setup")
        return redirect(url_for('setup'))
    
    # Reset asked questions for new interview
    session['asked_questions'] = []
    session.modified = True
    print("🔄 Reset asked_questions for new interview")
    
    # Additional debug info
    print(f"✅ Session valid, proceeding with interview")
    print(f"   Session ID: {session.get('session_id')}")
    print(f"   Name: {session.get('name')}")
    print(f"   Job description: {session.get('job_description', 'Not set')}")
    
    # Get actual values from session
    actual_num_questions = session.get('num_questions', 1)
    actual_minutes_per_question = session.get('minutes_per_question', 1)
    
    print(f"   Using session values - Questions: {actual_num_questions}, Minutes per question: {actual_minutes_per_question}")
    
    return render_template('interview.html', 
                         session_id=session.get('session_id'),
                         num_questions=actual_num_questions,
                         minutes_per_question=actual_minutes_per_question)

@app.route('/test')
def test():
    """Simple test page"""
    return render_template('test.html')

@app.route('/feedback')
def feedback():
    """Feedback Analytics Page - Page 4 with AI-powered insights"""
    if 'session_id' not in session:
        return redirect(url_for('setup'))
    
    # Get actual interview data if available, otherwise use mock data
    interview_data = session.get('interview_data', {})
    
    # Retrieve full job description from temporary storage if available
    session_id = session.get('session_id')
    full_job_description = session.get('job_description', '')  # fallback to truncated version
    if session_id and session_id in temp_data_store:
        full_job_description = temp_data_store[session_id].get('full_job_description', full_job_description)
    
    # Calculate realistic scores based on actual performance
    def calculate_realistic_scores(data):
        """Calculate realistic scores based on actual interview performance"""
        
        print(f"Calculating scores for data: {data}")
        
        # Get performance metrics
        total_words = data.get('total_words', 0)
        total_speaking_time = data.get('total_speaking_time', 0)  # in seconds
        total_questions = data.get('total_questions', 1)
        questions_answered = data.get('questions_answered', 0)
        questions_skipped = data.get('questions_skipped', 0)
        
        print(f"Performance metrics - Words: {total_words}, Speaking time: {total_speaking_time}s, Questions answered: {questions_answered}/{total_questions}")
        
        # Get the actual transcript for AI analysis
        transcript_data = data.get('transcript', [])
        combined_responses = " ".join([entry.get('response', '') for entry in transcript_data])
        
        # Initialize scores
        speech_score = 0
        posture_score = 0
        overall_score = 0
        ai_feedback = ""
        
        # Critical requirement: Check for minimal speaking time
        if total_speaking_time < 10:  # Reduced from 30s to 10s for testing
            print(f"WARNING: Speaking time {total_speaking_time}s < 10s minimum - but proceeding with analysis")
            # Still proceed with analysis but note the timing issue
        
        # Check if user provided meaningful responses based on transcript content
        transcript_data = data.get('transcript', [])
        total_response_length = sum(len(entry.get('response', '')) for entry in transcript_data)
        
        if questions_answered == 0 or total_words < 5 or total_response_length < 20:
            print(f"WARNING: Limited responses - Words: {total_words}, Response length: {total_response_length}")
            # Still analyze what we have instead of returning 0
            
        # Use AI to analyze the transcript and provide scoring
        try:
            if USE_AI_ANALYSIS:
                job_description = session.get('job_description', 'General position')
                session_id = session.get('session_id', '')
                
                # Get full job description if available
                if session_id in temp_data_store:
                    full_job_description = temp_data_store[session_id].get('full_job_description', job_description)
                else:
                    full_job_description = job_description
                
                ai_analysis = analyze_transcript_with_ai(combined_responses, full_job_description, data)
                
                # Extract AI scores and feedback
                speech_score = ai_analysis.get('speech_score', 0)
                overall_score = ai_analysis.get('overall_score', 0)
                ai_feedback = ai_analysis.get('feedback', '')
                
                print(f"✅ AI Analysis Complete - Speech: {speech_score}, Overall: {overall_score}")
            else:
                print("🔄 Using intelligent scoring without AI API")
                scores_result = calculate_enhanced_scores(data)
                speech_score = scores_result['speech_score']
                overall_score = scores_result['overall_score']
                ai_feedback = scores_result['feedback']
                
        except Exception as e:
            print(f"❌ AI analysis failed: {e}")
            # Fallback to enhanced scoring
            scores_result = calculate_enhanced_scores(data)
            speech_score = scores_result['speech_score']
            overall_score = scores_result['overall_score']
            ai_feedback = scores_result['feedback']
        
        # Calculate posture score from video data
        posture_data = data.get('posture_data', [])
        posture_score = calculate_posture_score(posture_data)
        
        return {
            'speech_score': int(speech_score),
            'posture_score': int(posture_score),
            'overall_score': int(overall_score),
            'ai_feedback': ai_feedback,
            'reason': f'Analysis complete - {len(transcript_data)} responses analyzed'
        }
    
    def analyze_transcript_with_ai(transcript, job_description, data):
        """Use Google Gemini AI to analyze interview transcript and provide scoring"""
        try:
            # Prepare analysis prompt with system instruction
            analysis_prompt = f"""You are an expert interview evaluator. Analyze this interview transcript and provide scores and feedback.
            
            Job Description: {job_description[:1000]}...
            
            Interview Transcript: {transcript[:1500]}...
            
            Additional Data:
            - Total words: {data.get('total_words', 0)}
            - Filler words: {data.get('filler_words', {})}
            - Questions answered: {data.get('questions_answered', 0)}/{data.get('total_questions', 1)}
            
            Please provide your analysis in this exact JSON format:
            {{
                "speech_score": [0-100 integer],
                "overall_score": [0-100 integer],
                "feedback": "Detailed feedback with specific improvements and strengths (max 200 words)"
            }}
            
            Consider: relevance to role, communication clarity, technical knowledge, completeness of answers. Provide constructive, specific feedback in valid JSON format only."""
            
            response = gemini_model.generate_content(analysis_prompt)
            ai_response = response.text.strip()
            print(f"🤖 Gemini Analysis Response: {ai_response}")
            
            # Parse the JSON response
            try:
                analysis_result = json.loads(ai_response)
                return analysis_result
            except json.JSONDecodeError:
                print("❌ Failed to parse Gemini response as JSON")
                return calculate_basic_scores_dict(data)
                
        except Exception as e:
            print(f"❌ AI analysis error: {e}")
            return calculate_basic_scores_dict(data)
    
    def calculate_basic_scores(data):
        """Fallback scoring method"""
        total_words = data.get('total_words', 0)
        questions_answered = data.get('questions_answered', 0)
        total_questions = data.get('total_questions', 1)
        
        # Basic scoring logic
        word_score = min(total_words * 0.8, 60)  # Max 60 points for words
        completion_score = (questions_answered / max(total_questions, 1)) * 40  # Max 40 points for completion
        
        speech_score = word_score + completion_score
        overall_score = speech_score * 0.8  # Slightly lower overall
        
        return speech_score, overall_score
    
    def calculate_basic_scores_dict(data):
        """Return basic scores in dictionary format"""
        speech_score, overall_score = calculate_basic_scores(data)
        return {
            'speech_score': speech_score,
            'overall_score': overall_score,
            'feedback': 'Basic analysis: Focus on providing more detailed responses and reducing filler words.'
        }
    
    def calculate_enhanced_scores(data):
        """Enhanced scoring system that works without AI API"""
        total_words = data.get('total_words', 0)
        questions_answered = data.get('questions_answered', 0)
        total_questions = data.get('total_questions', 1)
        transcript_data = data.get('transcript', [])
        
        # Calculate based on actual content quality
        total_response_length = sum(len(entry.get('response', '')) for entry in transcript_data)
        avg_confidence = sum(entry.get('confidence', 0) for entry in transcript_data) / max(len(transcript_data), 1)
        
        print(f"Enhanced scoring - Words: {total_words}, Response length: {total_response_length}, Confidence: {avg_confidence:.2f}")
        
        # Base score from word count (0-40 points)
        word_score = min(40, total_words * 0.4)
        
        # Response quality score (0-30 points) 
        if total_response_length > 150:
            response_score = 30
        elif total_response_length > 100:
            response_score = 25
        elif total_response_length > 50:
            response_score = 15
        else:
            response_score = max(5, total_response_length * 0.3)
        
        # Confidence score (0-20 points)
        confidence_score = avg_confidence * 20
        
        # Completion score (0-10 points)
        completion_score = 10 if len(transcript_data) > 0 else 0
        
        speech_score = word_score + response_score + confidence_score + completion_score
        
        # Generate intelligent feedback
        feedback_parts = []
        
        if speech_score >= 70:
            feedback_parts.append("Strong interview performance with clear, detailed responses.")
        elif speech_score >= 50:
            feedback_parts.append("Good communication with room for improvement in detail and structure.")
        else:
            feedback_parts.append("Consider providing more comprehensive responses with specific examples.")
            
        if total_words < 50:
            feedback_parts.append("Try to expand your answers with more detail and examples.")
        
        if avg_confidence < 0.8:
            feedback_parts.append("Practice speaking clearly and confidently to improve speech recognition accuracy.")
            
        filler_count = sum(data.get('filler_words', {}).values())
        if filler_count > 2:
            feedback_parts.append(f"Reduce filler words ({filler_count} detected) for more professional communication.")
        
        ai_feedback = " ".join(feedback_parts)
        
        # Calculate overall score (slightly lower than speech)
        overall_score = min(100, int(speech_score * 0.9))
        
        return {
            'speech_score': min(100, int(speech_score)),
            'overall_score': overall_score,
            'feedback': ai_feedback
        }
    
    def calculate_posture_score(posture_data):
        """Calculate posture score from video analysis data"""
        if not posture_data:
            return 50  # Default neutral score
        
        # Count positive vs negative posture indicators
        positive_count = 0
        total_count = len(posture_data)
        
        for entry in posture_data:
            posture_class = entry.get('posture_class', '').lower()
            if 'confident' in posture_class or 'good posture' in posture_class:
                positive_count += 1
        
        if total_count > 0:
            posture_percentage = (positive_count / total_count) * 100
            return min(max(posture_percentage, 10), 90)  # Cap between 10-90
        
        return 50
        posture_data = data.get('posture_data', [])
        if posture_data:
            # Calculate based on actual posture analysis
            good_posture_count = sum(1 for p in posture_data if 'Good Posture' in p.get('posture_class', '') or 'Confident' in p.get('posture_class', ''))
            total_posture_readings = len(posture_data)
            good_posture_ratio = good_posture_count / total_posture_readings if total_posture_readings > 0 else 0
            
            posture_score = int(good_posture_ratio * 80 + 10)  # 10-90 range
            
            # Bonus for consistency
            if good_posture_ratio > 0.8:
                posture_score += 10
        else:
            # Default posture score based on speech performance (if no video data)
            posture_score = max(20, int(speech_score * 0.6))  # Correlated with speech
        
        # Ensure posture score is within bounds
        posture_score = max(0, min(100, posture_score))
        
        # Overall score (weighted average + bonuses/penalties)
        overall_score = int((speech_score * 0.7) + (posture_score * 0.3))
        
        # Additional penalties for very poor performance
        if total_words < 20:
            overall_score = max(0, overall_score - 20)  # Severe penalty for very few words
        
        if questions_skipped > 0:
            overall_score = max(0, overall_score - (questions_skipped * 15))  # Penalty for skipping
        
        # Ensure overall score is within bounds
        overall_score = max(0, min(100, overall_score))
        
        print(f"Final scores - Speech: {speech_score}, Posture: {posture_score}, Overall: {overall_score}")
        
        return {
            'speech_score': speech_score,
            'posture_score': posture_score,
            'overall_score': overall_score,
            'metrics': {
                'words_per_question': round(words_per_question, 1),
                'speaking_time_per_question': round(speaking_time_per_question, 1),
                'completion_rate': round(completion_rate * 100, 1),
                'filler_words_total': filler_count
            }
        }
    
    scores = calculate_realistic_scores(interview_data)
    
    # Mock feedback data with realistic scores
    # Get transcript data, provide fallback if empty
    transcript_data = interview_data.get('transcript', [])
    if not transcript_data:
        # Create fallback transcript entry with correct format
        sample_response = interview_data.get('sample_response', 'No response recorded.')
        transcript_data = [{
            'question_number': 1,
            'question': 'Tell me about yourself.',
            'response': sample_response,
            'timestamp': '00:00:00',
            'duration': interview_data.get('total_speaking_time', 0),  # Use actual speaking time (number)
            'confidence': 0.5
        }]
    
    feedback_data = {
        'session_id': session.get('session_id'),
        'name': session.get('name'),
        'overall_score': scores['overall_score'],
        'ai_feedback': scores.get('ai_feedback', ''),  # Add AI-generated feedback
        'transcript': transcript_data,  # Use properly formatted transcript
        'total_words': interview_data.get('total_words', 0),
        'posture_data': interview_data.get('posture_data', []),  # Add posture timeline data
        'speech_analysis': {
            'score': scores['speech_score'],
            'total_words': interview_data.get('total_words', 0),
            'filler_words': interview_data.get('filler_words', {'um': 0, 'uh': 0, 'like': 0}),
            'speaking_pace': 'Too slow' if interview_data.get('total_words', 0) < 20 else 'Normal',
            'clarity': max(30, scores['speech_score'] - 10)
        },
        'body_language': {
            'posture_score': scores['posture_score'],
            'eye_contact': 'Needs improvement' if scores['posture_score'] < 50 else 'Good',
            'gestures': 'Minimal' if scores['posture_score'] < 50 else 'Appropriate'
        },
        # Additional scores for radar chart
        'response_time_score': scores.get('response_time_score', max(20, 80 - (interview_data.get('questions_skipped', 0) * 20))),
        'confidence_score': scores.get('confidence_score', int(sum([entry.get('confidence', 0.5) for entry in transcript_data]) / max(len(transcript_data), 1) * 100)),
        'content_score': scores.get('content_score', min(90, max(10, interview_data.get('total_words', 0) * 0.8)))
    }
    
    print(f"Feedback data being sent to template:")
    print(f"  Overall score: {feedback_data['overall_score']}")
    print(f"  Transcript entries: {len(feedback_data['transcript'])}")
    for i, item in enumerate(feedback_data['transcript']):
        print(f"    Entry {i}: duration={item.get('duration')} (type: {type(item.get('duration'))})")
        print(f"              response_length={len(item.get('response', ''))}")
    
    # Store session data for analytics
    session_analytics_data = {
        'name': session.get('name', 'Anonymous'),
        'session_id': session.get('session_id'),
        'job_description': full_job_description,
        'total_words': interview_data.get('total_words', 0),
        'questions_answered': interview_data.get('questions_answered', 0),
        'total_questions': interview_data.get('total_questions', 1),
        'filler_words': interview_data.get('filler_words', {}),
        'transcript': transcript_data
    }
    
    try:
        store_session_analytics(session_analytics_data, scores)
        print("✅ Session analytics data stored successfully")
    except Exception as e:
        print(f"❌ Failed to store analytics data: {e}")
    
    return render_template('feedback.html', data=feedback_data)

@app.route('/analytics')
def analytics():
    """Analytics Dashboard - Comprehensive progress tracking"""
    # Remove session restriction - allow access to analytics anytime
    user_name = session.get('name', 'Guest User')
    has_session = 'session_id' in session
    analytics_data = load_analytics_data()
    
    # Get user's analytics data
    user_data = analytics_data.get(user_name, {
        'sessions': [],
        'total_sessions': 0,
        'average_score': 0
    })
    
    # Calculate additional analytics metrics
    sessions = user_data.get('sessions', [])
    
    # Prepare data for charts
    analytics_info = {
        'user_name': user_name,
        'total_sessions': user_data.get('total_sessions', 0),
        'average_score': round(user_data.get('average_score', 0), 1),
        'sessions': sessions[-10:],  # Last 10 sessions for charts
        'improvement_trend': calculate_improvement_trend(sessions),
        'skill_breakdown': calculate_skill_breakdown(sessions),
        'recent_performance': calculate_recent_performance(sessions),
        'all_users_stats': calculate_all_users_stats(analytics_data),
        'has_session': has_session
    }
    
    return render_template('analytics.html', data=analytics_info)

def calculate_improvement_trend(sessions):
    """Calculate improvement trend over sessions"""
    if len(sessions) < 2:
        return 0
    
    # Calculate trend from first half to second half
    mid_point = len(sessions) // 2
    first_half_avg = sum([s['overall_score'] for s in sessions[:mid_point]]) / max(mid_point, 1)
    second_half_avg = sum([s['overall_score'] for s in sessions[mid_point:]]) / max(len(sessions) - mid_point, 1)
    
    return round(second_half_avg - first_half_avg, 1)

def calculate_skill_breakdown(sessions):
    """Calculate average scores for each skill category"""
    if not sessions:
        return {
            'speech': 0,
            'posture': 0,
            'confidence': 0,
            'content': 0,
            'response_time': 0
        }
    
    return {
        'speech': round(sum([s['speech_score'] for s in sessions]) / len(sessions), 1),
        'posture': round(sum([s['posture_score'] for s in sessions]) / len(sessions), 1),
        'confidence': round(sum([s['confidence_score'] for s in sessions]) / len(sessions), 1),
        'content': round(sum([s['content_score'] for s in sessions]) / len(sessions), 1),
        'response_time': round(sum([s['response_time_score'] for s in sessions]) / len(sessions), 1)
    }

def calculate_recent_performance(sessions):
    """Calculate performance metrics for recent sessions"""
    if not sessions:
        return {
            'best_score': 0,
            'worst_score': 0,
            'most_improved_skill': 'None',
            'total_questions': 0,
            'total_words': 0
        }
    
    recent_sessions = sessions[-5:]  # Last 5 sessions
    
    return {
        'best_score': max([s['overall_score'] for s in sessions]),
        'worst_score': min([s['overall_score'] for s in sessions]),
        'most_improved_skill': determine_most_improved_skill(sessions),
        'total_questions': sum([s['questions_answered'] for s in recent_sessions]),
        'total_words': sum([s['total_words'] for s in recent_sessions])
    }

def determine_most_improved_skill(sessions):
    """Determine which skill improved the most"""
    if len(sessions) < 3:
        return 'Need more sessions'
    
    skills = ['speech_score', 'posture_score', 'confidence_score', 'content_score', 'response_time_score']
    skill_names = ['Speech', 'Posture', 'Confidence', 'Content', 'Response Time']
    
    max_improvement = 0
    best_skill = 'None'
    
    for i, skill in enumerate(skills):
        # Compare first 3 sessions with last 3 sessions
        first_avg = sum([s[skill] for s in sessions[:3]]) / 3
        last_avg = sum([s[skill] for s in sessions[-3:]]) / 3
        improvement = last_avg - first_avg
        
        if improvement > max_improvement:
            max_improvement = improvement
            best_skill = skill_names[i]
    
    return best_skill

def calculate_all_users_stats(analytics_data):
    """Calculate statistics across all users for comparison"""
    all_sessions = []
    total_users = len(analytics_data)
    
    for user_data in analytics_data.values():
        all_sessions.extend(user_data.get('sessions', []))
    
    if not all_sessions:
        return {
            'total_users': 0,
            'average_score': 0,
            'total_sessions': 0,
            'top_performers': []
        }
    
    # Calculate top performers
    user_averages = []
    for user_name, user_data in analytics_data.items():
        if user_data.get('sessions'):
            avg_score = user_data.get('average_score', 0)
            user_averages.append((user_name, avg_score))
    
    top_performers = sorted(user_averages, key=lambda x: x[1], reverse=True)[:5]
    
    return {
        'total_users': total_users,
        'average_score': round(sum([s['overall_score'] for s in all_sessions]) / len(all_sessions), 1),
        'total_sessions': len(all_sessions),
        'top_performers': top_performers
    }

@app.route('/api/submit-interview', methods=['POST'])
def submit_interview():
    """Submit interview data for analysis"""
    data = request.get_json()
    
    print(f"Received interview data: {data}")
    
    # Store interview data in session for realistic scoring
    session['interview_data'] = {
        'total_words': data.get('total_words', 0),
        'total_speaking_time': data.get('total_speaking_time', 0),
        'total_questions': data.get('total_questions', 1),
        'questions_answered': data.get('questions_answered', 0),
        'questions_skipped': data.get('questions_skipped', 0),
        'transcript': data.get('transcript', []),
        'filler_words': data.get('filler_words', {'um': 0, 'uh': 0, 'like': 0}),
        'posture_data': data.get('posture_data', []),
        'sample_response': data.get('sample_response', 'No response recorded.')
    }
    
    print(f"Stored interview data in session: {session['interview_data']}")
    
    # If we have real speech analysis data, integrate it
    if data.get('real_speech_analysis'):
        speech_analysis = data['real_speech_analysis']
        # Update with real analysis results
        session['interview_data'].update({
            'real_transcription': speech_analysis.get('transcript', ''),
            'real_speech_score': speech_analysis.get('final_score', 0),
            'real_speaking_rate': speech_analysis.get('speaking_rate', 0),
            'real_performance_level': speech_analysis.get('performance_level', 'Unknown')
        })
        print(f"Integrated real speech analysis: score={speech_analysis.get('final_score', 0)}")
    
    return jsonify({'status': 'success', 'message': 'Interview data saved'})

@app.route('/api/reset-questions', methods=['POST'])
def reset_questions():
    """Reset the asked questions list for a fresh interview start"""
    session['asked_questions'] = []
    session.modified = True
    print("🔄 Questions reset via API call")
    return jsonify({'status': 'success', 'message': 'Questions reset'})

@app.route('/api/generate-question')
def generate_question():
    """Generate AI-powered questions based on job description using Google Gemini"""
    job_description = session.get('job_description', 'Software Developer')
    session_id = session.get('session_id', '')
    
    print(f"🔍 Session ID: {session_id}")
    print(f"🔍 Current session keys: {list(session.keys())}")
    
    # Initialize or get asked questions list
    if 'asked_questions' not in session:
        session['asked_questions'] = []
        print("🆕 Initialized new asked_questions list")
    
    asked_questions = session['asked_questions']
    current_question_number = len(asked_questions) + 1
    
    print(f"🔍 Already asked {len(asked_questions)} questions: {asked_questions}")
    print(f"🔍 Generating question #{current_question_number}")
    
    # Force a fresh start if this is the first request and we have old questions
    if current_question_number == 1 and len(asked_questions) > 0:
        print("🔄 Detected stale session, forcing fresh start")
        session['asked_questions'] = []
        asked_questions = []
        session.modified = True
    
    # Get full job description from temp storage if available
    if session_id in temp_data_store:
        full_job_description = temp_data_store[session_id].get('full_job_description', job_description)
    else:
        full_job_description = job_description
    
    # Analyze experience level and determine question type
    def analyze_job_level(job_desc):
        """Analyze job description to determine experience level"""
        job_lower = job_desc.lower()
        
        # Entry level indicators
        entry_keywords = ['entry level', 'junior', 'graduate', 'internship', 'trainee', 'beginner', 
                         'new grad', 'fresh', 'starter', '0-1 year', '0-2 year', 'recent graduate']
        
        # Senior level indicators  
        senior_keywords = ['senior', 'lead', 'principal', 'architect', 'manager', 'director',
                          '5+ year', '7+ year', '10+ year', 'expert', 'advanced', 'leadership']
        
        # Check for entry level
        if any(keyword in job_lower for keyword in entry_keywords):
            return 'entry'
        # Check for senior level
        elif any(keyword in job_lower for keyword in senior_keywords):
            return 'senior'
        else:
            return 'mid'  # Default to mid-level
    
    def determine_question_type(question_number, total_behavioral_ratio=0.6):
        """Determine if question should be behavioral or technical based on 60/40 split"""
        # For first few questions, ensure good mix
        if question_number <= 3:
            return 'behavioral' if question_number % 2 == 1 else 'technical'
        
        # For later questions, use ratio-based approach
        behavioral_count = sum(1 for q in asked_questions if 'tell me about' in q.lower() or 'describe a time' in q.lower())
        total_asked = len(asked_questions)
        
        if total_asked == 0:
            return 'behavioral'
        
        current_behavioral_ratio = behavioral_count / total_asked
        return 'behavioral' if current_behavioral_ratio < total_behavioral_ratio else 'technical'
    
    experience_level = analyze_job_level(full_job_description)
    question_type = determine_question_type(current_question_number)
    
    print(f"🎯 Experience level: {experience_level}")
    print(f"🎯 Question type: {question_type}")

    # Use intelligent fallback questions based on job description keywords
    try:
        if USE_AI_ANALYSIS:
            # Create context about previously asked questions
            previously_asked = "\n".join([f"- {q}" for q in asked_questions]) if asked_questions else "None"
            
            # Use Google Gemini to generate contextual interview questions
            # Add variety to questions by including question categories
            question_categories = {
                'behavioral': [
                    'teamwork and collaboration', 'problem-solving and challenges', 'leadership and initiative', 
                    'conflict resolution', 'adaptability and change', 'communication skills', 'career goals and motivation',
                    'learning and development', 'work under pressure', 'project management'
                ],
                'technical': [
                    'core skills and expertise', 'tools and technologies', 'best practices and methodologies',
                    'troubleshooting and debugging', 'optimization and efficiency', 'quality assurance',
                    'system design and architecture', 'data analysis and reporting', 'automation and scripting'
                ]
            }
            
            import random
            available_categories = question_categories.get(question_type, question_categories['behavioral'])
            chosen_category = random.choice(available_categories)
            
            prompt = f"""You are an expert interview coach. Generate a unique interview question and helpful hint in STRICT JSON format.

Job Description: {full_job_description[:2000]}

Experience Level: {experience_level}
Question Type Required: {question_type}
Focus Category: {chosen_category}
Question Number: {current_question_number}

Previously Asked Questions:
{previously_asked}

CRITICAL REQUIREMENTS:
1. Generate a COMPLETELY DIFFERENT question from previously asked ones - use varied topics and approaches
2. Focus on the category: "{chosen_category}" - create questions around this specific theme
3. Question MUST match the experience level:
   - Entry level: Basic concepts, fundamental understanding, simple scenarios
   - Mid level: Practical application, problem-solving, moderate complexity  
   - Senior level: Strategic thinking, leadership scenarios, complex challenges
4. Question MUST be the specified type:
   - Behavioral: Focus on past experiences, soft skills, team situations, problem-solving stories
   - Technical: Focus on job-relevant skills, tools, processes, domain knowledge
5. Keep questions conversational and approachable - avoid overly complex jargon
6. Include a helpful answering hint (2-3 sentences) that guides the candidate
7. Respond ONLY with valid JSON - no extra text, no markdown, no explanations
8. Use exactly this format:

{{"question": "Your user-friendly interview question here", "hint": "Your helpful hint that guides the candidate on how to structure their answer"}}

Do not include any text before or after the JSON."""
            
            response = gemini_model.generate_content(prompt)
            ai_response = response.text.strip()
            
            print(f"🔍 Raw Gemini response: {ai_response}")
            
            try:
                # Clean up the response - remove any markdown formatting or extra text
                import json
                import re
                
                # Try to extract JSON from the response
                json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    response_data = json.loads(json_str)
                    question = response_data.get('question', '').strip()
                    hint = response_data.get('hint', '').strip()
                    
                    if question and hint:
                        print(f"✅ Successfully parsed JSON - Question: {question[:50]}...")
                        print(f"✅ Successfully parsed JSON - Hint: {hint[:50]}...")
                    else:
                        raise ValueError("Missing question or hint in JSON")
                        
                else:
                    raise ValueError("No valid JSON found in response")
                    
            except (json.JSONDecodeError, ValueError) as e:
                print(f"⚠️ JSON parsing failed: {e}")
                print("🔄 Using fallback question generation")
                
                # Check if the response looks like raw JSON text being displayed
                if ai_response.startswith('```json') or '{"question":' in ai_response:
                    # Try to extract question from malformed JSON response
                    try:
                        # Look for question pattern in the text
                        question_match = re.search(r'"question":\s*"([^"]+)"', ai_response)
                        hint_match = re.search(r'"hint":\s*"([^"]+)"', ai_response)
                        
                        if question_match:
                            question = question_match.group(1).strip()
                            hint = hint_match.group(1).strip() if hint_match else 'Take your time to think through your response and provide specific examples.'
                        else:
                            raise ValueError("Could not extract question from malformed JSON")
                    except:
                        # Final fallback - don't use AI response if it's malformed
                        question = None
                        hint = None
                else:
                    # If it's not JSON-like, treat as a simple question
                    question = ai_response.strip()
                    hint = 'Take your time to think through your response and provide specific examples from your experience.'
            
            # Validate that we have a proper question
            if not question or len(question.strip()) < 10 or question.startswith('```') or question.startswith('{'):
                print(f"⚠️ Generated question is invalid: '{question}' (length: {len(question.strip()) if question else 0})")
                print("🔄 Falling back to structured questions")
                raise ValueError("Invalid question generated")
            
            # Track the question to avoid repeats
            session['asked_questions'].append(question)
            session.modified = True
            
            print(f"✅ Gemini-generated question: {question}")
            print(f"✅ Generated hint: {hint}")
            
            return jsonify({'question': question, 'hint': hint})
        else:
            print("🔄 Using intelligent fallback questions")
            
    except Exception as e:
        print(f"❌ Error generating Gemini question: {e}")
        print("🔄 Using intelligent fallback questions")
        
    # Enhanced fallback to contextual questions based on job description keywords and experience level
    job_lower = full_job_description.lower()
    
    # Create experience-appropriate questions
    if 'data analyst' in job_lower or 'data' in job_lower or 'analytics' in job_lower:
        if experience_level == 'entry':
            fallback_questions = [
                {"question": "What drew you to data analysis as a career?", "hint": "Share your interest in working with data and any relevant coursework, projects, or experiences.", "type": "behavioral"},
                {"question": "Can you walk me through how you would approach cleaning a messy dataset?", "hint": "Describe basic steps like checking for duplicates, missing values, and data types.", "type": "technical"},
                {"question": "Tell me about a time you had to learn a new tool or skill quickly.", "hint": "Use the STAR method and focus on your learning approach and persistence.", "type": "behavioral"},
                {"question": "How would you explain what data analysis means to someone non-technical?", "hint": "Use simple terms and maybe give a relatable example from everyday life.", "type": "technical"},
                {"question": "Describe a project where you used data to answer a question.", "hint": "This could be from school, internship, or personal project. Focus on your process and findings.", "type": "behavioral"},
                {"question": "What's your experience with Excel or Google Sheets for data work?", "hint": "Mention specific functions you've used like pivot tables, VLOOKUP, or basic formulas.", "type": "technical"}
            ]
        elif experience_level == 'senior':
            fallback_questions = [
                {"question": "How do you approach building data strategy for an organization?", "hint": "Discuss stakeholder alignment, infrastructure needs, and long-term vision.", "type": "technical"},
                {"question": "Tell me about a time you had to influence executives using data insights.", "hint": "Focus on how you presented complex data in an executive-friendly way and the impact.", "type": "behavioral"},
                {"question": "How do you mentor junior analysts and build analytical capabilities in a team?", "hint": "Share specific examples of coaching others and developing team skills.", "type": "behavioral"},
                {"question": "Describe how you handle conflicting data requirements from different stakeholders.", "hint": "Discuss prioritization frameworks and communication strategies you use.", "type": "behavioral"},
                {"question": "What's your approach to building scalable data solutions?", "hint": "Talk about architecture decisions, automation, and planning for growth.", "type": "technical"},
                {"question": "How do you ensure data governance and quality across multiple teams?", "hint": "Discuss processes, tools, and cultural changes you've implemented.", "type": "technical"}
            ]
        else:  # mid-level
            fallback_questions = [
                {"question": "Describe your experience with data analysis tools like Python, R, or SQL.", "hint": "Mention specific libraries or techniques you've used in real projects.", "type": "technical"},
                {"question": "Tell me about a time you found an unexpected insight in your data analysis.", "hint": "Use STAR method and explain how you investigated and validated the finding.", "type": "behavioral"},
                {"question": "How do you handle situations where stakeholders want data to support their pre-existing conclusions?", "hint": "Discuss maintaining objectivity and communicating findings diplomatically.", "type": "behavioral"},
                {"question": "Walk me through your process for data visualization and reporting.", "hint": "Describe your step-by-step approach from data to final presentation.", "type": "technical"},
                {"question": "Describe a challenging data project and how you overcame obstacles.", "hint": "Focus on problem-solving skills and technical solutions you implemented.", "type": "behavioral"},
                {"question": "How do you validate and ensure the accuracy of your analysis?", "hint": "Discuss quality checks, validation techniques, and peer review processes.", "type": "technical"}
            ]
    elif 'software' in job_lower or 'developer' in job_lower or 'programming' in job_lower:
        if experience_level == 'entry':
            fallback_questions = [
                {"question": "What programming languages are you most comfortable with?", "hint": "Mention specific languages and any projects or coursework where you used them.", "type": "technical"},
                {"question": "Tell me about a coding project you're proud of.", "hint": "This could be from school, bootcamp, or personal learning. Focus on what you built and learned.", "type": "behavioral"},
                {"question": "How do you approach debugging when your code isn't working?", "hint": "Describe your step-by-step process, like reading error messages and using print statements.", "type": "technical"},
                {"question": "Describe a time you had to learn a new technology or framework.", "hint": "Share your learning approach and how you applied it to a project.", "type": "behavioral"},
                {"question": "What resources do you use to improve your programming skills?", "hint": "Mention specific websites, tutorials, books, or communities you find helpful.", "type": "behavioral"},
                {"question": "Can you explain the difference between a class and an object?", "hint": "Use simple terms and maybe give a real-world analogy to explain the concept.", "type": "technical"}
            ]
        elif experience_level == 'senior':
            fallback_questions = [
                {"question": "How do you approach architectural decisions for complex software systems?", "hint": "Discuss trade-offs, scalability considerations, and decision-making frameworks you use.", "type": "technical"},
                {"question": "Tell me about a time you had to mentor junior developers.", "hint": "Focus on specific coaching techniques and how you helped them grow technically.", "type": "behavioral"},
                {"question": "How do you handle technical debt and legacy code in large codebases?", "hint": "Discuss prioritization strategies and gradual improvement approaches.", "type": "technical"},
                {"question": "Describe how you lead technical discussions and build consensus.", "hint": "Share examples of facilitating architectural reviews or technical decision-making.", "type": "behavioral"},
                {"question": "What's your approach to ensuring code quality across a development team?", "hint": "Discuss code review processes, standards, and tools you've implemented.", "type": "technical"},
                {"question": "How do you balance technical excellence with business delivery pressures?", "hint": "Share examples of making pragmatic technical decisions under time constraints.", "type": "behavioral"}
            ]
        else:  # mid-level
            fallback_questions = [
                {"question": "Describe your experience with version control and collaborative development.", "hint": "Mention specific Git workflows, branching strategies, and code review practices.", "type": "technical"},
                {"question": "Tell me about a challenging bug you had to solve.", "hint": "Use STAR method and focus on your debugging process and problem-solving approach.", "type": "behavioral"},
                {"question": "How do you ensure your code is maintainable and readable?", "hint": "Discuss coding standards, documentation, and design principles you follow.", "type": "technical"},
                {"question": "Describe a time you had to optimize application performance.", "hint": "Explain the performance issue, your analysis approach, and specific improvements made.", "type": "behavioral"},
                {"question": "What's your approach to testing and quality assurance?", "hint": "Discuss different testing types and frameworks you've used in your projects.", "type": "technical"},
                {"question": "How do you stay current with new technologies and best practices?", "hint": "Mention specific resources, conferences, or learning approaches you use regularly.", "type": "behavioral"}
            ]
    else:
        # General questions based on experience level
        if experience_level == 'entry':
            fallback_questions = [
                {"question": "Tell me about yourself and what interests you about this role.", "hint": "Give a brief summary of your background and connect it to why you want this specific position.", "type": "behavioral"},
                {"question": "What skills do you bring that would help you succeed in this position?", "hint": "Focus on relevant skills from school, internships, or projects that match the job requirements.", "type": "behavioral"},
                {"question": "Describe a challenging project or assignment you've completed.", "hint": "This could be from school, internship, or personal learning. Use STAR method to structure your answer.", "type": "behavioral"},
                {"question": "How do you approach learning new skills or technologies?", "hint": "Share your learning process and give a specific example of something you recently learned.", "type": "behavioral"},
                {"question": "Tell me about a time you worked in a team.", "hint": "Focus on your specific role, how you contributed, and what the team accomplished together.", "type": "behavioral"},
                {"question": "What do you know about our company and why do you want to work here?", "hint": "Share what you've researched about the company and how it aligns with your career goals.", "type": "behavioral"}
            ]
        elif experience_level == 'senior':
            fallback_questions = [
                {"question": "How do you approach strategic planning and long-term vision in your field?", "hint": "Discuss frameworks you use for strategic thinking and examples of long-term initiatives you've led.", "type": "behavioral"},
                {"question": "Tell me about a time you had to lead through a major organizational change.", "hint": "Focus on your leadership approach, communication strategies, and how you helped others adapt.", "type": "behavioral"},
                {"question": "How do you develop and mentor high-performing teams?", "hint": "Share specific examples of building team capabilities and developing individual contributors.", "type": "behavioral"},
                {"question": "Describe how you handle competing priorities and resource constraints.", "hint": "Discuss prioritization frameworks and examples of making tough resource allocation decisions.", "type": "behavioral"},
                {"question": "What's your approach to driving innovation and continuous improvement?", "hint": "Share examples of initiatives you've led to improve processes or introduce new approaches.", "type": "behavioral"},
                {"question": "How do you build relationships with stakeholders at different organizational levels?", "hint": "Discuss communication strategies and examples of successful stakeholder management.", "type": "behavioral"}
            ]
        else:  # mid-level
            fallback_questions = [
                {"question": "Tell me about yourself and your professional journey so far.", "hint": "Highlight key experiences and skills that are most relevant to this role.", "type": "behavioral"},
                {"question": "Describe a project where you took ownership and drove results.", "hint": "Use STAR method and focus on your initiative, problem-solving, and impact.", "type": "behavioral"},
                {"question": "How do you handle competing deadlines and prioritize your work?", "hint": "Share specific strategies and tools you use for time management and prioritization.", "type": "behavioral"},
                {"question": "Tell me about a time you had to collaborate across different teams or departments.", "hint": "Focus on communication skills and how you built consensus or resolved conflicts.", "type": "behavioral"},
                {"question": "Describe a situation where you had to adapt to unexpected changes.", "hint": "Highlight your flexibility and problem-solving approach when plans changed.", "type": "behavioral"},
                {"question": "What professional development activities do you pursue to grow your skills?", "hint": "Mention specific learning approaches, courses, or experiences that have helped you advance.", "type": "behavioral"}
            ]
    
    # Filter questions by type to maintain 60/40 behavioral/technical ratio
    behavioral_questions = [q for q in fallback_questions if q.get('type') == 'behavioral' and q["question"] not in asked_questions]
    technical_questions = [q for q in fallback_questions if q.get('type') == 'technical' and q["question"] not in asked_questions]
    
    # Choose question based on determined type
    if question_type == 'behavioral' and behavioral_questions:
        available_questions = behavioral_questions
    elif question_type == 'technical' and technical_questions:
        available_questions = technical_questions
    else:
        # Fallback to any available questions if preferred type is not available
        available_questions = [q for q in fallback_questions if q["question"] not in asked_questions]
    
    print(f"📝 Total fallback questions: {len(fallback_questions)}")
    print(f"📝 Available questions after filtering: {len(available_questions)}")
    print(f"📝 Already asked: {asked_questions}")
    
    if not available_questions:
        # If all questions have been asked, create a general follow-up question
        question_data = {
            "question": "Is there anything else you'd like to share about your qualifications for this role?",
            "hint": "This is your opportunity to highlight any relevant skills or experiences we haven't discussed yet."
        }
        print("🔄 All questions used, using final question")
    else:
        import random
        question_data = random.choice(available_questions)
        print(f"🎲 Randomly selected from {len(available_questions)} available questions")
    
    # Track the question to avoid repeats
    session['asked_questions'].append(question_data["question"])
    session.modified = True
    
    print(f"🎯 Using contextual question: {question_data['question']}")
    print(f"📋 Updated asked_questions list: {session['asked_questions']}")
    
    return jsonify({'question': question_data["question"], 'hint': question_data["hint"]})

@app.route('/api/analyze-speech', methods=['POST'])
def analyze_speech():
    """Send audio data to backend speech analysis service and accumulate per-chunk transcript locally for feedback page."""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400

        audio_file = request.files['audio']
        session_id = session.get('session_id', 'unknown')

        # Ensure interview_data exists
        if 'interview_data' not in session:
            session['interview_data'] = {
                'total_words': 0,
                'total_speaking_time': 0.0,
                'total_questions': session.get('num_questions', 1),
                'questions_answered': 0,
                'questions_skipped': 0,
                'transcript': [],
                'filler_words': {'um': 0, 'uh': 0, 'like': 0},
                'posture_data': []
            }

        print(f"Received audio file for analysis: {audio_file.filename}")

        # Try real backend
        try:
            files = {'audio': (audio_file.filename, audio_file.stream, audio_file.content_type)}
            data = {'session_id': session_id}

            response = requests.post(
                f"{BACKEND_API_URL}/api/analysis/speech-analysis",
                files=files, data=data, timeout=30
            )

            if response.status_code != 200:
                print(f"❌ Backend request failed: {response.status_code} {response.text}")
                raise Exception(f"Backend returned status {response.status_code}")

            backend_result = response.json()
            analysis_data = backend_result.get('analysis', {})

            # Map backend -> frontend chunk
            transcript_text = analysis_data.get('transcript_chunk', '') or ''
            perf = analysis_data.get('performance_metrics', {}) or {}
            aq = analysis_data.get('audio_quality', {}) or {}
            fw = analysis_data.get('filler_words', {}) or {}
            duration = analysis_data.get('duration', 0.0) or 0.0  # we added this in speech_service; defensively default to 0
            confidence = analysis_data.get('confidence', 0.9)

            # Build transcript entry expected by feedback.html
            transcript_entry = {
                'question_number': len(session['interview_data']['transcript']) + 1,
                'question': session.get('last_question', ''),  # optional if you track it
                'response': transcript_text,
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'duration': duration,  # number → template formats mm:ss
                'confidence': confidence
            }

            # Update session interview_data
            idata = session['interview_data']
            idata['transcript'].append(transcript_entry)
            idata['total_words'] += int(perf.get('word_count', 0) or 0)
            idata['total_speaking_time'] += float(duration)
            # merge filler words if present
            breakdown = fw.get('breakdown', {})
            for k in ('um', 'uh', 'like'):
                idata['filler_words'][k] = idata['filler_words'].get(k, 0) + int(breakdown.get(k, 0) or 0)

            # Consider a chunk “answered” if it has words
            if perf.get('word_count', 0):
                idata['questions_answered'] = max(idata.get('questions_answered', 0), transcript_entry['question_number'])

            session['interview_data'] = idata
            session.modified = True

            # Return a simplified analysis for the calling JS
            formatted_analysis = {
                'transcript': transcript_text,
                'final_score': int(perf.get('final_score', 0) or 0),
                'speaking_rate': int(aq.get('speaking_rate', 0) or 0),
                'filler_count': int(fw.get('count', 0) or 0),
                'filler_rate': float(perf.get('filler_rate', 0.0) or 0.0),
                'performance_level': perf.get('performance_level', 'Unknown'),
                'word_count': int(perf.get('word_count', 0) or 0),
                'analysis_type': analysis_data.get('analysis_type', 'real_backend_integration'),
                'confidence': confidence,
                'duration': duration,
            }
            return jsonify({'status': 'success', 'analysis': formatted_analysis})

        except requests.exceptions.RequestException as e:
            print(f"❌ Backend connection failed: {e}")
            print("⚠️ Falling back to mock analysis")

            mock_analysis = {
                'transcript': 'Backend unavailable - using mock transcription',
                'final_score': 75,
                'speaking_rate': 150,
                'filler_count': 2,
                'filler_rate': 0.03,
                'performance_level': 'Good',
                'word_count': 45,
                'analysis_type': 'mock_fallback_backend_unavailable',
                'confidence': 0.5,
                'duration': 1.0
            }

            # Also append mock to session so feedback has data
            idata = session['interview_data']
            idata['transcript'].append({
                'question_number': len(idata['transcript']) + 1,
                'question': session.get('last_question', ''),
                'response': mock_analysis['transcript'],
                'timestamp': datetime.now().strftime("%H:%M:%S"),
                'duration': mock_analysis['duration'],
                'confidence': mock_analysis['confidence']
            })
            idata['total_words'] += mock_analysis['word_count']
            idata['total_speaking_time'] += mock_analysis['duration']
            for k in ('um', 'uh', 'like'):
                idata['filler_words'][k] = idata['filler_words'].get(k, 0) + (1 if k in ('um','uh') else 0)
            session['interview_data'] = idata
            session.modified = True

            return jsonify({'status': 'success', 'analysis': mock_analysis})

    except Exception as e:
        print(f"Error in speech analysis: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    host = os.getenv("FRONTEND_HOST", "0.0.0.0")
    port = int(os.getenv("FRONTEND_PORT", 5000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(debug=debug, host=host, port=port)
