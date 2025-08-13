"""
Video Analysis Service for PrepWise
Handles posture detection and body language analysis using the trained model
"""

import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoAnalysisService:
    def __init__(self):
        """Initialize the video analysis service with the trained model"""
        self.model = None
        self.model_path = None
        self.initialize_model()
    
    def initialize_model(self):
        """Load the trained posture detection model"""
        try:
            # Get the correct path to the video model
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Navigate to the video models directory within PrepWise
            video_models_path = os.path.join(current_dir, '..', 'models', 'video')
            self.model_path = os.path.join(video_models_path, 'final_best_model.h5')
            
            # Normalize the path
            self.model_path = os.path.normpath(self.model_path)
            
            if os.path.exists(self.model_path):
                logger.info(f"Loading model from: {self.model_path}")
                self.model = load_model(self.model_path)
                logger.info("Video analysis model loaded successfully!")
            else:
                logger.error(f"Model file not found at: {self.model_path}")
                logger.info("Using mock video analysis for now")
                self.model = None
                
        except Exception as e:
            logger.error(f"Error loading video model: {e}")
            logger.info("Falling back to mock video analysis")
            self.model = None
    
    def analyze_frame(self, frame):
        """
        Analyze a single video frame for posture detection
        
        Args:
            frame: OpenCV frame (numpy array)
            
        Returns:
            dict: Analysis results including posture classification
        """
        try:
            if self.model is None:
                return self._mock_analysis()
            
            # Preprocess frame for model
            processed_frame = self._preprocess_frame(frame)
            
            # Make prediction
            prediction = self.model.predict(processed_frame, verbose=0)
            
            # Get the predicted class
            predicted_class = np.argmax(prediction[0])
            confidence = float(np.max(prediction[0]))
            
            # Map class indices to labels (based on your actual model training)
            class_labels = {
                0: "Good Posture",
                1: "Slouching", 
                2: "Confident Expression",
                3: "Nervous Expression"
            }
            
            posture_label = class_labels.get(predicted_class, "Unknown")
            
            # Calculate posture score based on classification
            if "Good" in posture_label or "Confident" in posture_label:
                posture_score = int(80 + (confidence * 20))
            else:
                posture_score = int(40 - (confidence * 20))
            
            return {
                'posture_class': posture_label,
                'posture_score': max(10, min(100, posture_score)),
                'confidence': confidence,
                'timestamp': cv2.getTickCount() / cv2.getTickFrequency()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing frame: {e}")
            return self._mock_analysis()
    
    def _preprocess_frame(self, frame):
        """
        Preprocess frame for model input
        Adjust based on your model's requirements
        """
        try:
            # Resize frame (adjust dimensions based on your model)
            resized = cv2.resize(frame, (224, 224))  # Common size for CNN models
            
            # Normalize pixel values
            normalized = resized.astype(np.float32) / 255.0
            
            # Add batch dimension
            batched = np.expand_dims(normalized, axis=0)
            
            return batched
            
        except Exception as e:
            logger.error(f"Error preprocessing frame: {e}")
            return None
    
    def _mock_analysis(self):
        """Provide mock analysis when model is not available"""
        import random
        
        # Use correct posture classes
        postures = ["Good Posture", "Slouching", "Confident Expression", "Nervous Expression"]
        selected_posture = random.choice(postures)
        
        # Give realistic scores based on actual classes
        if "Good Posture" in selected_posture or "Confident Expression" in selected_posture:
            score = random.randint(70, 90)
        else:  # Slouching or Nervous Expression
            score = random.randint(30, 60)
        
        return {
            'posture_class': selected_posture,
            'posture_score': score,
            'confidence': random.uniform(0.6, 0.9),
            'timestamp': cv2.getTickCount() / cv2.getTickFrequency(),
            'is_mock': True
        }
    
    def analyze_video_stream(self, video_frames):
        """
        Analyze a sequence of video frames
        
        Args:
            video_frames: List of OpenCV frames
            
        Returns:
            dict: Comprehensive analysis results
        """
        if not video_frames:
            return {'error': 'No frames provided'}
        
        frame_analyses = []
        
        for i, frame in enumerate(video_frames):
            if i % 10 == 0:  # Analyze every 10th frame to reduce processing
                analysis = self.analyze_frame(frame)
                frame_analyses.append(analysis)
        
        if not frame_analyses:
            return {'error': 'No frames could be analyzed'}
        
        # Aggregate results
        posture_scores = [a['posture_score'] for a in frame_analyses]
        avg_posture_score = sum(posture_scores) / len(posture_scores)
        
        # Count posture classifications
        posture_counts = {}
        for analysis in frame_analyses:
            posture = analysis['posture_class']
            posture_counts[posture] = posture_counts.get(posture, 0) + 1
        
        # Determine dominant posture
        dominant_posture = max(posture_counts, key=posture_counts.get)
        
        return {
            'average_posture_score': int(avg_posture_score),
            'dominant_posture': dominant_posture,
            'posture_distribution': posture_counts,
            'total_frames_analyzed': len(frame_analyses),
            'frame_analyses': frame_analyses[-5:],  # Return last 5 for details
            'model_status': 'active' if self.model else 'mock'
        }

# Global instance
video_service = VideoAnalysisService()

def get_video_service():
    """Get the global video analysis service instance"""
    return video_service
