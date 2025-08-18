# app/services/video_service.py
import os, logging
from typing import Dict, Any, Optional
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)

# Optional deps
try:
    import cv2
except Exception:
    cv2 = None
try:
    import tensorflow as tf
except Exception:
    tf = None

# Try both import paths depending on your layout
try:
    from models.video.detection_utils import ActionDetector
    from models.video.config import ACTIONS
except Exception:
    from app.models.video.detection_utils import ActionDetector  # type: ignore
    from app.models.video.config import ACTIONS  # type: ignore


class VideoAnalysisService:
    """
    Loads final_best_model.h5 (if available), runs ActionDetector (MediaPipe Holistic + LSTM)
    over 30-frame sequences, and tracks per-session posture distribution.
    Falls back to 'Neutral' if TF/OpenCV/model are missing.
    """
    def __init__(self):
        self.initialized: bool = False
        self.model = None
        self.detector: Optional[ActionDetector] = None
        self.model_path = os.getenv("VIDEO_MODEL_PATH", "models/video/final_best_model.h5")
        self.posture_distribution: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    async def initialize(self):
        if self.initialized:
            return
        if tf is None or cv2 is None:
            logger.warning("TensorFlow/OpenCV missing; video model disabled (Neutral posture only).")
            self.initialized = True
            return
        if not os.path.exists(self.model_path):
            logger.warning("Video model not found at %s; video model disabled.", self.model_path)
            self.initialized = True
            return
        try:
            self.model = tf.keras.models.load_model(self.model_path)
            self.detector = ActionDetector(model=self.model, sequence_length=30, threshold=0.6)
            logger.info("Loaded video model: %s", self.model_path)
        except Exception as e:
            logger.error("Failed to load video model: %s", e)
            self.model = None
            self.detector = None
        self.initialized = True
        logger.info("VideoAnalysisService initialized.")

    async def cleanup(self):
        try:
            if self.detector:
                self.detector.cleanup()
        except Exception:
            pass
        self.detector = None
        self.model = None
        self.initialized = False

    def _bump(self, session_id: str, label: str):
        self.posture_distribution[session_id][label] += 1

    async def analyze_frame(self, image_bytes: bytes, session_id: str) -> Dict[str, Any]:
        """Accept JPEG/PNG bytes. Returns {posture_classification, metrics:{confidence}}."""
        if cv2 is None or self.detector is None:
            self._bump(session_id, "Neutral")
            return {"posture_classification": "Neutral", "metrics": {"confidence": 0.3}}

        np_bytes = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(np_bytes, cv2.IMREAD_COLOR)
        if frame is None:
            self._bump(session_id, "Neutral")
            return {"posture_classification": "Neutral", "metrics": {"confidence": 0.2}}

        _, pred = self.detector.detect_action(frame)  # predicts once seq len == 30
        if pred is None:
            self._bump(session_id, "Neutral")
            return {"posture_classification": "Neutral", "metrics": {"confidence": 0.4}}

        idx = int(pred.get("predicted_class", 0))
        conf = float(pred.get("confidence", 0.0))
        try:
            cls_name = ACTIONS[idx]
        except Exception:
            cls_name = f"class_{idx}"

        self._bump(session_id, cls_name)
        return {"posture_classification": cls_name, "metrics": {"confidence": conf}}

    def get_distribution(self, session_id: str) -> Dict[str, int]:
        return dict(self.posture_distribution.get(session_id, {}))

    def reset_session(self, session_id: str):
        self.posture_distribution.pop(session_id, None)
