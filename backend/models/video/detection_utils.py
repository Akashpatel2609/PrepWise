"""
Real-time detection utilities for Action Detection System
"""
import cv2
import numpy as np
import mediapipe as mp
import logging
import os
from .config import COLORS, ACTIONS

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MediaPipeDetector:
    def __init__(self, detection_confidence=0.5, tracking_confidence=0.5):
        self.mp_holistic = mp.solutions.holistic
        self.mp_drawing = mp.solutions.drawing_utils
        self.holistic = self.mp_holistic.Holistic(
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence
        )
    
    def mediapipe_detection(self, image):
        """Perform MediaPipe detection"""
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        results = self.holistic.process(image)  # Use self.holistic instance, not self.mp_holistic
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image, results
    
    def draw_styled_landmarks(self, image, results):
        """Draw styled landmarks on image"""
        # Draw face connections
        self.mp_drawing.draw_landmarks(
            image,
            results.face_landmarks,
            mp.solutions.face_mesh.FACEMESH_TESSELATION,
            self.mp_drawing.DrawingSpec(color=(80,110,10), thickness=1, circle_radius=1),
            self.mp_drawing.DrawingSpec(color=(80,256,121), thickness=1, circle_radius=1)
        )
        
        # Draw pose connections
        self.mp_drawing.draw_landmarks(
            image, results.pose_landmarks, self.mp_holistic.POSE_CONNECTIONS,
            self.mp_drawing.DrawingSpec(color=(80,22,10), thickness=2, circle_radius=4),
            self.mp_drawing.DrawingSpec(color=(80,44,121), thickness=2, circle_radius=2)
        )
        
        # Draw left hand connections
        self.mp_drawing.draw_landmarks(
            image, results.left_hand_landmarks, self.mp_holistic.HAND_CONNECTIONS,
            self.mp_drawing.DrawingSpec(color=(121,22,76), thickness=2, circle_radius=4),
            self.mp_drawing.DrawingSpec(color=(121,44,250), thickness=2, circle_radius=2)
        )
        
        # Draw right hand connections
        self.mp_drawing.draw_landmarks(
            image, results.right_hand_landmarks, self.mp_holistic.HAND_CONNECTIONS,
            self.mp_drawing.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=4),
            self.mp_drawing.DrawingSpec(color=(245,66,230), thickness=2, circle_radius=2)
        )
    
    def extract_keypoints(self, results):
        """Extract keypoints from MediaPipe results"""
        pose = np.array([[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark]).flatten() if results.pose_landmarks else np.zeros(33*4)
        face = np.array([[res.x, res.y, res.z] for res in results.face_landmarks.landmark]).flatten() if results.face_landmarks else np.zeros(468*3)
        lh = np.array([[res.x, res.y, res.z] for res in results.left_hand_landmarks.landmark]).flatten() if results.left_hand_landmarks else np.zeros(21*3)
        rh = np.array([[res.x, res.y, res.z] for res in results.right_hand_landmarks.landmark]).flatten() if results.right_hand_landmarks else np.zeros(21*3)
        return np.concatenate([pose, face, lh, rh])
    
    def __del__(self):
        """Cleanup resources"""
        self.cleanup()
    
    def cleanup(self):
        """Cleanup MediaPipe resources"""
        if hasattr(self, 'holistic') and self.holistic:
            try:
                self.holistic.close()
                self.holistic = None
            except (ValueError, AttributeError):
                # Already closed or None
                pass

class ProbabilityVisualizer:
    def __init__(self, actions=ACTIONS, colors=COLORS):
        self.actions = actions
        self.colors = colors
    
    def prob_viz(self, res, input_frame):
        """Visualize prediction probabilities on frame"""
        output_frame = input_frame.copy()
        
        for num, prob in enumerate(res):
            # Convert probability to scalar
            prob_scalar = float(np.squeeze(prob))
            
            # Draw probability bar
            cv2.rectangle(
                output_frame, 
                (0, 60 + num * 40), 
                (int(prob_scalar * 100), 90 + num * 40), 
                self.colors[num % len(self.colors)], 
                -1
            )
            
            # Draw action label
            cv2.putText(
                output_frame, 
                self.actions[num], 
                (0, 85 + num * 40), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                1, 
                (255, 255, 255), 
                2, 
                cv2.LINE_AA
            )
        
        return output_frame

class ActionDetector:
    def __init__(self, model, sequence_length=30, threshold=0.7):
        self.model = model
        self.sequence_length = sequence_length
        self.threshold = threshold
        self.sequence = []
        self.sentence = []
        self.predictions = []
        self.detector = MediaPipeDetector()
        self.visualizer = ProbabilityVisualizer()
        # Load normalization stats if available
        self.feature_mean = None
        self.feature_std = None
        try:
            mean_path = os.path.join('processed_data', 'feature_mean.npy')
            std_path = os.path.join('processed_data', 'feature_std.npy')
            if os.path.exists(mean_path) and os.path.exists(std_path):
                self.feature_mean = np.load(mean_path)
                self.feature_std = np.load(std_path)
                # Guard against zeros
                self.feature_std = np.where(self.feature_std == 0, 1e-8, self.feature_std)
                logging.info("Inference normalization stats loaded (z-score).")
            else:
                logging.warning("Normalization stats not found; using raw keypoints for inference.")
        except Exception as e:
            logging.warning(f"Could not load normalization stats: {e}")
    
    def detect_action(self, frame):
        """Detect action from frame"""
        try:
            # Make detection
            image, results = self.detector.mediapipe_detection(frame)
            
            # Draw landmarks
            self.detector.draw_styled_landmarks(image, results)
            
            # Extract keypoints
            keypoints = self.detector.extract_keypoints(results)
            self.sequence.append(keypoints)
            self.sequence = self.sequence[-self.sequence_length:]
            
            prediction_result = None
            
            if len(self.sequence) == self.sequence_length:
                seq_array = np.array(self.sequence)  # shape (T, F)
                if self.feature_mean is not None and self.feature_std is not None and seq_array.shape[-1] == self.feature_mean.shape[0]:
                    norm_seq = (seq_array - self.feature_mean) / self.feature_std
                else:
                    norm_seq = seq_array
                # Make prediction on normalized (or raw) sequence
                res = self.model.predict(np.expand_dims(norm_seq, axis=0), verbose=0)[0]
                self.predictions.append(np.argmax(res))
                
                # Logic for stable predictions
                if len(self.predictions) >= 10:
                    recent_predictions = self.predictions[-10:]
                    if len(np.unique(recent_predictions)) == 1:  # All same prediction
                        if res[np.argmax(res)] > self.threshold:
                            predicted_action = ACTIONS[np.argmax(res)]
                            
                            if len(self.sentence) > 0:
                                if predicted_action != self.sentence[-1]:
                                    self.sentence.append(predicted_action)
                            else:
                                self.sentence.append(predicted_action)
                
                # Keep sentence length manageable
                if len(self.sentence) > 5:
                    self.sentence = self.sentence[-5:]
                
                # Visualize probabilities
                image = self.visualizer.prob_viz(res, image)
                prediction_result = {
                    'probabilities': res,
                    'predicted_class': np.argmax(res),
                    'confidence': res[np.argmax(res)],
                    'action': ACTIONS[np.argmax(res)]
                }
            
            # Draw sentence
            cv2.rectangle(image, (0, 0), (640, 40), (245, 117, 16), -1)
            cv2.putText(
                image, 
                ' '.join(self.sentence), 
                (3, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 
                1, 
                (255, 255, 255), 
                2, 
                cv2.LINE_AA
            )
            
            return image, prediction_result
            
        except Exception as e:
            logger.error(f"Error in detect_action: {str(e)}")
            return frame, None
    
    def reset(self):
        """Reset detection state"""
        self.sequence = []
        self.sentence = []
        self.predictions = []
    
    def cleanup(self):
        """Cleanup MediaPipe resources"""
        if self.detector:
            self.detector.cleanup()
    
    def __del__(self):
        """Cleanup on deletion"""
        self.cleanup()

def main():
    """Test the detection utilities"""
    detector = MediaPipeDetector()
    print("MediaPipe detector initialized")
    
    visualizer = ProbabilityVisualizer()
    print("Probability visualizer initialized")

if __name__ == "__main__":
    main()
